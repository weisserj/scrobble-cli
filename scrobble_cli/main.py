from __future__ import annotations

from datetime import datetime

import questionary
import typer
from rich.console import Console
from rich.table import Table

from scrobble_cli.config import config_summary, load_config, write_config_values
from scrobble_cli.discogs import fetch_release, search_query
from scrobble_cli.lastfm import ScrobbleTrack, ensure_session, scrobble_album
from scrobble_cli.matching import discogs_query_confidence, discogs_title_confidence
from scrobble_cli.timestamps import plan_from_end, plan_from_start


app = typer.Typer(no_args_is_help=True, add_completion=False)
auth_app = typer.Typer(no_args_is_help=True)
app.add_typer(auth_app, name="auth")

console = Console()


@app.command()
def status():
  """Show config status (masked)."""
  cfg = load_config()
  console.print(config_summary(cfg))


@auth_app.command("discogs")
def auth_discogs(token: str = typer.Option(None, help="Discogs personal access token (recommended)")):
  """Save Discogs token to your local config."""
  if not token:
    token = typer.prompt("Discogs token", hide_input=True)
  path = write_config_values({"DISCOGS_TOKEN": token})
  console.print(f"Wrote Discogs token to {path}")


@auth_app.command("lastfm")
def auth_lastfm(
  api_key: str = typer.Option(None, help="Last.fm API key (or set LASTFM_API_KEY)"),
  api_secret: str = typer.Option(None, help="Last.fm API secret (or set LASTFM_API_SECRET)"),
):
  """Authorize with Last.fm (token flow, no password)."""
  cfg = load_config()
  if not api_key:
    api_key = cfg.lastfm.api_key or typer.prompt("Last.fm API key", hide_input=True)
  if not api_secret:
    api_secret = cfg.lastfm.api_secret or typer.prompt("Last.fm API secret", hide_input=True)

  try:
    ensure_session(cfg, api_key=api_key, api_secret=api_secret)
  except RuntimeError as e:
    console.print(str(e))
    raise typer.Exit(code=2)

  console.print("Last.fm auth complete.")


def _render_results(results):
  table = Table(title="Discogs matches", show_lines=False)
  table.add_column("#", justify="right", style="bold")
  table.add_column("Title")
  table.add_column("Year", justify="right")
  table.add_column("Format")
  table.add_column("Label")
  table.add_column("Cat#", overflow="fold")
  table.add_column("Type", justify="center")
  for i, r in enumerate(results, start=1):
    table.add_row(
      str(i),
      r.title,
      str(r.year or ""),
      r.format or "",
      r.label or "",
      r.catno or "",
      r.kind,
    )
  console.print(table)


@app.command("album")
def scrobble_album_command(
  query: list[str] = typer.Argument(
    ...,
    help='Album query. Prefix with "ended" to scrobble as if you finished listening (e.g. `scrobble album ended barney wilen moshi`).',
  ),
  artist: str | None = typer.Option(None, "--artist", help="Optional artist (improves auto-match confidence)"),
  album: str | None = typer.Option(None, "--album", help="Optional album (improves auto-match confidence)"),
  started_at: str | None = typer.Option(
    None,
    "--started-at",
    help='ISO timestamp for when listening started (e.g. "2026-01-31T19:32:00"). Defaults to now.',
  ),
  ended_at: str | None = typer.Option(
    None,
    "--ended-at",
    help='Optional ISO timestamp for when listening ended (e.g. "2026-01-31T19:32:00"). Defaults to now.',
  ),
  vinyl_only: bool = typer.Option(True, "--vinyl/--any-format", help="Prefer vinyl matches on Discogs"),
  limit: int = typer.Option(10, "--max-results", min=1, max=25),
  auto: bool = typer.Option(True, "--auto/--no-auto", help="Auto-pick only when extremely confident"),
  yes: bool = typer.Option(False, "-y", "--yes", help="Skip confirmation prompt"),
  dry_run: bool = typer.Option(False, "--dry-run", help="Print what would be scrobbled, but do not call Last.fm"),
  allow_ignored: bool = typer.Option(
    False, "--allow-ignored", help="Exit 0 even if Last.fm ignores some tracks (still prints details)"
  ),
):
  """
  Scrobble an album by looking up its tracklist on Discogs, then submitting a single batch to Last.fm.
  Defaults to "started now" timestamping (prefix the query with `ended` to use the previous behavior).
  """
  cfg = load_config()
  try:
    cfg = ensure_session(cfg, api_key=None, api_secret=None)
  except RuntimeError as e:
    console.print(str(e))
    console.print("Run `scrobble auth lastfm` first.")
    raise typer.Exit(code=2)

  tokens = [t for t in query if t is not None]
  mode = "started"
  if tokens and tokens[0].lower() in ("ended", "end", "finish", "finished"):
    mode = "ended"
    tokens = tokens[1:]
  elif tokens and tokens[0].lower() in ("started", "start", "begin", "beginning"):
    mode = "started"
    tokens = tokens[1:]

  query_str = " ".join(tokens).strip()
  if not query_str:
    console.print("Missing query.")
    raise typer.Exit(code=2)

  results = search_query(cfg, query=query_str, vinyl_only=vinyl_only, limit=limit)
  if not results:
    raise typer.Exit(code=2)

  selected = None
  if auto:
    top = results[0]
    if artist and album:
      confidence = discogs_title_confidence(artist=artist, album=album, discogs_title=top.title)
    else:
      confidence = discogs_query_confidence(query=query_str, discogs_title=top.title)
    if confidence >= 0.92:
      selected = top

  if not selected:
    _render_results(results)
    choices = [f"{i}. {r.title} [{r.kind}] {r.year or ''}".strip() for i, r in enumerate(results, start=1)]
    picked = questionary.select("Pick the correct release:", choices=choices).ask()
    if not picked:
      raise typer.Exit(code=1)
    idx = int(picked.split(".", 1)[0]) - 1
    selected = results[idx]

  release = fetch_release(cfg, kind=selected.kind, id=selected.id)
  if not release.tracks:
    console.print("No tracklist found on Discogs for that selection.")
    raise typer.Exit(code=2)

  default_duration = 240
  durations = [(t.duration_seconds or default_duration) for t in release.tracks]
  now_unix = int(datetime.now().timestamp())

  if mode == "ended":
    if started_at:
      console.print("`--started-at` can't be used with `album ended ...`.")
      raise typer.Exit(code=2)
    if ended_at:
      try:
        dt = datetime.fromisoformat(ended_at)
      except ValueError:
        console.print('Invalid `--ended-at`. Use ISO format like "2026-01-31T19:32:00".')
        raise typer.Exit(code=2)
      end_unix = int(dt.timestamp())
    else:
      end_unix = now_unix
    timestamps = plan_from_end(end_unix, durations)
  else:
    if ended_at:
      console.print("`--ended-at` can't be used unless you prefix the query with `ended`.")
      raise typer.Exit(code=2)
    if started_at:
      try:
        dt = datetime.fromisoformat(started_at)
      except ValueError:
        console.print('Invalid `--started-at`. Use ISO format like "2026-01-31T19:32:00".')
        raise typer.Exit(code=2)
      start_unix = int(dt.timestamp())
    else:
      start_unix = now_unix
    timestamps = plan_from_start(start_unix, durations)

  scrobbles: list[ScrobbleTrack] = []
  for t, ts in zip(release.tracks, timestamps, strict=True):
    scrobbles.append(
      ScrobbleTrack(
        artist=release.artist,
        title=t.title,
        album=release.album,
        album_artist=release.artist,
        timestamp_unix=ts,
        duration_seconds=t.duration_seconds,
      )
    )

  preview = Table(title=f"{release.artist} — {release.album}", show_lines=False)
  preview.add_column("#", justify="right")
  preview.add_column("Pos", justify="right")
  preview.add_column("Title")
  preview.add_column("Dur", justify="right")
  for i, t in enumerate(release.tracks, start=1):
    d = t.duration_seconds
    dur = "" if d is None else f"{d//60}:{d%60:02d}"
    preview.add_row(str(i), t.position or "", t.title, dur)
  console.print(preview)

  if not yes and not (auto and selected == results[0]):
    ok = questionary.confirm(f"Scrobble {len(scrobbles)} tracks to Last.fm now?").ask()
    if not ok:
      raise typer.Exit(code=1)

  if dry_run:
    console.print("Dry run: not calling Last.fm.")
    raise typer.Exit(code=0)

  res = scrobble_album(cfg, scrobbles)
  console.print("Submitted to Last.fm.")

  ignored_items: list[tuple[str, str, str]] = []
  ts_to_discogs = {}
  for i, (t, ts) in enumerate(zip(release.tracks, timestamps, strict=True), start=1):
    ts_to_discogs[int(ts)] = (t.position or str(i), t.title, t.duration_seconds)

  for b in res.get("batches") or []:
    if "error" in b:
      console.print(f"Last.fm error: {b.get('message')}")
      raise typer.Exit(code=3)
    scrobbles_obj = (b.get("scrobbles") or {}).get("scrobble")
    if isinstance(scrobbles_obj, dict):
      scrobbles_obj = [scrobbles_obj]
    for s in scrobbles_obj or []:
      ignored_msg = s.get("ignoredMessage") or {}
      code = str(ignored_msg.get("code") or "0")
      if code == "0":
        continue

      try:
        ts = int(s.get("timestamp"))
      except Exception:
        ts = None

      track_obj = s.get("track")
      if isinstance(track_obj, dict):
        title = str(track_obj.get("#text") or "")
      else:
        title = str(track_obj or "")

      reason = str(ignored_msg.get("#text") or "").strip() or f"ignoredMessage.code={code}"

      if ts is not None and ts in ts_to_discogs:
        pos, discogs_title, discogs_dur = ts_to_discogs[ts]
        title = discogs_title or title
        if discogs_dur is not None and discogs_dur < 30:
          reason = f"{reason} (likely too short for Last.fm)"
      else:
        pos = ""

      ignored_items.append((pos, title, reason))

  if ignored_items:
    table = Table(title="Ignored by Last.fm", show_lines=False)
    table.add_column("Pos", justify="right")
    table.add_column("Title")
    table.add_column("Reason", overflow="fold")
    for pos, title, reason in ignored_items:
      table.add_row(pos, title, reason)
    console.print(table)
    console.print(f"{len(ignored_items)} track(s) were ignored by Last.fm.")
    if not allow_ignored:
      console.print("Treating as failure (use `--allow-ignored` to ignore this).")
      raise typer.Exit(code=4)


if __name__ == "__main__":
  app()

