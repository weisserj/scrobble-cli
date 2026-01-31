# Contributing

Thanks for wanting to help!

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

## Running locally

- `scrobble --help`
- `scrobble status`
- `scrobble album ... --dry-run`

## Secrets / safety

Please do **not** include secrets in commits, issues, screenshots, or logs.

- Don’t paste `DISCOGS_TOKEN`, `LASTFM_API_SECRET`, session keys, or auth URLs containing tokens.
- If you need to reproduce a bug, redact output (or use placeholder values).

Before opening a PR, it’s worth running:

```bash
rg -n "LASTFM_|DISCOGS_|api_secret|session_key|token=" -S .
```

## Pull requests

- Keep changes focused (one feature/bugfix per PR).
- Update `README.md` if behavior/flags change.
- Prefer adding small helper functions over adding new dependencies.

