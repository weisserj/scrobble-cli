from __future__ import annotations

import re
from dataclasses import dataclass

import requests

from scrobble_cli.config import AppConfig


DISCOGS_API = "https://api.discogs.com"


def _duration_to_seconds(duration: str) -> int | None:
  if not duration:
    return None
  duration = duration.strip()
  if not duration:
    return None
  if duration.isdigit():
    return int(duration)
  m = re.match(r"^(?:(\d+):)?(\d+):(\d+)$", duration)
  if m:
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2))
    seconds = int(m.group(3))
    return hours * 3600 + minutes * 60 + seconds
  m2 = re.match(r"^(\d+):(\d+)$", duration)
  if m2:
    minutes = int(m2.group(1))
    seconds = int(m2.group(2))
    return minutes * 60 + seconds
  return None


_re_discogs_disambiguation = re.compile(r"\s+\(\d+\)$")


def _clean_artist_name(name: str) -> str:
  return _re_discogs_disambiguation.sub("", (name or "").strip())


@dataclass(frozen=True)
class DiscogsSearchResult:
  id: int
  kind: str  # "master" or "release"
  title: str
  year: int | None
  country: str | None
  label: str | None
  catno: str | None
  format: str | None


@dataclass(frozen=True)
class DiscogsTrack:
  position: str | None
  title: str
  duration_seconds: int | None


@dataclass(frozen=True)
class DiscogsRelease:
  id: int
  kind: str
  artist: str
  album: str
  year: int | None
  tracks: list[DiscogsTrack]


def _headers(cfg: AppConfig) -> dict[str, str]:
  h = {
    "User-Agent": "scrobble-cli/0.1.0",
    "Accept": "application/json",
  }
  if cfg.discogs.token:
    h["Authorization"] = f"Discogs token={cfg.discogs.token}"
  return h


def _get(cfg: AppConfig, path: str, params: dict | None = None) -> dict:
  if not cfg.discogs.token:
    raise RuntimeError("Missing Discogs token. Set DISCOGS_TOKEN or run `scrobble auth discogs`.")
  url = f"{DISCOGS_API}{path}"
  r = requests.get(url, headers=_headers(cfg), params=params, timeout=30)
  r.raise_for_status()
  return r.json()


def search(cfg: AppConfig, *, artist: str, album: str, vinyl_only: bool, limit: int) -> list[DiscogsSearchResult]:
  q = f"{artist} {album}".strip()
  base: dict[str, str | int] = {"q": q, "per_page": limit, "page": 1}
  if vinyl_only:
    base["format"] = "Vinyl"

  def run(kind: str) -> list[DiscogsSearchResult]:
    params = dict(base)
    params["type"] = kind
    data = _get(cfg, "/database/search", params=params)
    out: list[DiscogsSearchResult] = []
    for item in data.get("results") or []:
      item_kind = item.get("type")
      if item_kind not in ("master", "release"):
        continue
      fmt = None
      if isinstance(item.get("format"), list) and item.get("format"):
        fmt = ", ".join(item["format"])

      label = None
      if isinstance(item.get("label"), list) and item.get("label"):
        label = item["label"][0]

      out.append(
        DiscogsSearchResult(
          id=int(item["id"]),
          kind=item_kind,
          title=str(item.get("title") or ""),
          year=int(item["year"]) if item.get("year") else None,
          country=str(item["country"]) if item.get("country") else None,
          label=label,
          catno=str(item.get("catno")) if item.get("catno") else None,
          format=fmt,
        )
      )
    return out

  results = run("master")
  if not results:
    results = run("release")
  return results


def search_query(cfg: AppConfig, *, query: str, vinyl_only: bool, limit: int) -> list[DiscogsSearchResult]:
  query = (query or "").strip()
  if not query:
    return []
  return search(cfg, artist=query, album="", vinyl_only=vinyl_only, limit=limit)


def _split_title(title: str) -> tuple[str, str]:
  if " - " in title:
    a, b = title.split(" - ", 1)
    return a.strip(), b.strip()
  return title.strip(), title.strip()


def fetch_release(cfg: AppConfig, *, kind: str, id: int) -> DiscogsRelease:
  if kind == "master":
    data = _get(cfg, f"/masters/{id}")
  elif kind == "release":
    data = _get(cfg, f"/releases/{id}")
  else:
    raise ValueError("kind must be 'master' or 'release'")

  artist, album = _split_title(str(data.get("title") or ""))

  if kind == "master":
    album = str(data.get("title") or "").strip()
    artists = data.get("artists") or []
    if artists and isinstance(artists, list):
      artist = _clean_artist_name(str(artists[0].get("name") or ""))

  tracklist = data.get("tracklist") or []
  tracks: list[DiscogsTrack] = []
  for t in tracklist:
    if (t.get("type_") or t.get("type")) != "track":
      continue
    title = str(t.get("title") or "").strip()
    if not title:
      continue
    tracks.append(
      DiscogsTrack(
        position=str(t.get("position") or "").strip() or None,
        title=title,
        duration_seconds=_duration_to_seconds(str(t.get("duration") or "")),
      )
    )

  return DiscogsRelease(
    id=id,
    kind=kind,
    artist=_clean_artist_name(artist),
    album=album,
    year=int(data["year"]) if data.get("year") else None,
    tracks=tracks,
  )
