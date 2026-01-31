from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from platformdirs import user_config_path


def _mask(value: str | None) -> str:
  if not value:
    return ""
  if len(value) <= 6:
    return "***"
  return f"{value[:3]}***{value[-3:]}"


@dataclass(frozen=True)
class LastFmConfig:
  api_key: str | None
  api_secret: str | None
  session_key: str | None
  username: str | None


@dataclass(frozen=True)
class DiscogsConfig:
  token: str | None


@dataclass(frozen=True)
class AppConfig:
  lastfm: LastFmConfig
  discogs: DiscogsConfig


def config_dir() -> Path:
  return Path(user_config_path("scrobble-cli"))


def legacy_config_dir() -> Path:
  return Path(user_config_path("scrobbler-cli"))


def config_path() -> Path:
  return config_dir() / "config.env"


def legacy_config_path() -> Path:
  return legacy_config_dir() / "config.env"


def _maybe_migrate_legacy_config() -> None:
  """
  If the user already configured the old name (scrobbler-cli), keep working without forcing re-auth.
  """
  new_path = config_path()
  old_path = legacy_config_path()
  if new_path.exists() or not old_path.exists():
    return
  config_dir().mkdir(parents=True, exist_ok=True)
  new_path.write_text(old_path.read_text(encoding="utf-8"), encoding="utf-8")
  os.chmod(new_path, 0o600)


def load_config() -> AppConfig:
  """
  Loads from:
  - env vars (preferred for CI / temporary usage)
  - config file at ~/.config/scrobble-cli/config.env (macOS will differ via platformdirs)
  """
  _maybe_migrate_legacy_config()

  file_values: dict[str, str] = {}
  for path in (config_path(), legacy_config_path()):
    if not path.exists():
      continue
    for raw in path.read_text(encoding="utf-8").splitlines():
      line = raw.strip()
      if not line or line.startswith("#"):
        continue
      if "=" not in line:
        continue
      k, v = line.split("=", 1)
      file_values.setdefault(k.strip(), v.strip())

  def get(name: str) -> str | None:
    return os.environ.get(name) or file_values.get(name)

  return AppConfig(
    lastfm=LastFmConfig(
      api_key=get("LASTFM_API_KEY"),
      api_secret=get("LASTFM_API_SECRET"),
      session_key=get("LASTFM_SESSION_KEY"),
      username=get("LASTFM_USERNAME"),
    ),
    discogs=DiscogsConfig(
      token=get("DISCOGS_TOKEN"),
    ),
  )


def write_config_values(values: dict[str, str | None]) -> Path:
  config_dir().mkdir(parents=True, exist_ok=True)
  path = config_path()

  existing: dict[str, str] = {}
  if path.exists():
    for raw in path.read_text(encoding="utf-8").splitlines():
      line = raw.strip()
      if not line or line.startswith("#") or "=" not in line:
        continue
      k, v = line.split("=", 1)
      existing[k.strip()] = v.strip()

  for k, v in values.items():
    if v is None:
      continue
    existing[k] = v

  lines = [
    "# scrobble-cli config (do not commit)",
    "# You can also set these as env vars instead.",
  ]
  for k in sorted(existing.keys()):
    lines.append(f"{k}={existing[k]}")

  path.write_text("\n".join(lines) + "\n", encoding="utf-8")
  os.chmod(path, 0o600)
  return path


def config_summary(cfg: AppConfig) -> str:
  return "\n".join(
    [
      "Last.fm:",
      f"  LASTFM_API_KEY={_mask(cfg.lastfm.api_key)}",
      f"  LASTFM_API_SECRET={_mask(cfg.lastfm.api_secret)}",
      f"  LASTFM_SESSION_KEY={_mask(cfg.lastfm.session_key)}",
      f"  LASTFM_USERNAME={cfg.lastfm.username or ''}",
      "Discogs:",
      f"  DISCOGS_TOKEN={_mask(cfg.discogs.token)}",
      f"  Config file={config_path()}",
    ]
  )
