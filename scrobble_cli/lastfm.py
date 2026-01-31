from __future__ import annotations

import hashlib
import time
import webbrowser
from dataclasses import dataclass

import requests

from scrobble_cli.config import AppConfig, load_config, write_config_values


LASTFM_API = "https://ws.audioscrobbler.com/2.0/"


def _sig(params: dict[str, str], api_secret: str) -> str:
  """
  Last.fm signature: concatenate key+value for all params (sorted by key),
  excluding "format" and "callback", then append secret; MD5 hex.
  """
  parts: list[str] = []
  for k in sorted(params.keys()):
    if k in ("format", "callback"):
      continue
    parts.append(k)
    parts.append(params[k])
  parts.append(api_secret)
  raw = "".join(parts).encode("utf-8")
  return hashlib.md5(raw).hexdigest()


def _post(params: dict[str, str]) -> dict:
  r = requests.post(LASTFM_API, data=params, timeout=30)
  r.raise_for_status()
  return r.json()


@dataclass(frozen=True)
class ScrobbleTrack:
  artist: str
  title: str
  album: str
  album_artist: str
  timestamp_unix: int
  duration_seconds: int | None = None


def ensure_session(cfg: AppConfig, *, api_key: str | None, api_secret: str | None) -> AppConfig:
  """
  Ensures we have a Last.fm session key without ever asking for a Last.fm password.
  Uses auth.getToken + user authorizes in browser + auth.getSession.
  """
  key = api_key or cfg.lastfm.api_key
  secret = api_secret or cfg.lastfm.api_secret
  if not key or not secret:
    raise RuntimeError("Missing Last.fm API key/secret. Set LASTFM_API_KEY and LASTFM_API_SECRET.")

  if cfg.lastfm.session_key and cfg.lastfm.username and (cfg.lastfm.api_key == key) and (cfg.lastfm.api_secret == secret):
    return cfg

  token_params = {"method": "auth.getToken", "api_key": key, "format": "json"}
  token_params["api_sig"] = _sig(token_params, secret)
  token = _post(token_params).get("token")
  if not token:
    raise RuntimeError("Failed to obtain Last.fm token.")

  auth_url = f"https://www.last.fm/api/auth/?api_key={key}&token={token}"
  webbrowser.open(auth_url)
  input(f"Authorize in your browser, then press Enter to continue:\n{auth_url}\n> ")

  session_params = {"method": "auth.getSession", "api_key": key, "token": token, "format": "json"}
  session_params["api_sig"] = _sig(session_params, secret)
  session_data = _post(session_params)
  session = session_data.get("session") or {}
  username = session.get("name")
  session_key = session.get("key")
  if not username or not session_key:
    msg = session_data.get("message") or "Last.fm authentication failed."
    raise RuntimeError(msg)

  write_config_values(
    {
      "LASTFM_API_KEY": key,
      "LASTFM_API_SECRET": secret,
      "LASTFM_SESSION_KEY": session_key,
      "LASTFM_USERNAME": username,
    }
  )
  return load_config()


def scrobble_album(cfg: AppConfig, tracks: list[ScrobbleTrack]) -> dict:
  if not cfg.lastfm.api_key or not cfg.lastfm.api_secret or not cfg.lastfm.session_key:
    raise RuntimeError("Missing Last.fm config. Run `scrobble auth lastfm` first.")

  if not tracks:
    raise RuntimeError("No tracks to scrobble.")

  # Last.fm track.scrobble supports up to 50 tracks per request.
  results: list[dict] = []
  for offset in range(0, len(tracks), 50):
    batch = tracks[offset : offset + 50]
    params: dict[str, str] = {
      "method": "track.scrobble",
      "api_key": cfg.lastfm.api_key,
      "sk": cfg.lastfm.session_key,
      "format": "json",
    }
    for i, t in enumerate(batch):
      params[f"artist[{i}]"] = t.artist
      params[f"track[{i}]"] = t.title
      params[f"album[{i}]"] = t.album
      params[f"albumArtist[{i}]"] = t.album_artist
      params[f"timestamp[{i}]"] = str(int(t.timestamp_unix))
      if t.duration_seconds:
        params[f"duration[{i}]"] = str(int(t.duration_seconds))

    params["api_sig"] = _sig(params, cfg.lastfm.api_secret)
    res = _post(params)
    results.append(res)

    time.sleep(0.2)

  return {"batches": results}

