Scrobble a vinyl record to Last.fm using scrobble-cli: $ARGUMENTS

The scrobble-cli wrapper lives at `SCROBBLE_CLI_PATH/scrobble-wrapper.sh`. All commands go through this wrapper (it handles venv activation).

**After copying this file to `~/.claude/commands/scrobble.md`, replace every `SCROBBLE_CLI_PATH` with the absolute path to your scrobble-cli clone (e.g., `/Users/you/repos/scrobble-cli`).**

## How to scrobble

### Step 1: Search for the album

Run the search command to get JSON results (non-interactive):

```
SCROBBLE_CLI_PATH/scrobble-wrapper.sh album <query> --search-only
```

If the query starts with `ended`, pass it through as part of the query (e.g., `scrobble-wrapper.sh album ended miles davis kind of blue --search-only`). This tells the CLI to timestamp as "just finished listening" instead of "started now".

### Step 2: Present results and ask the user

Show the user the search results (artist, title, year, format, country) and ask which release number to pick. The results are 1-indexed.

### Step 3: Execute the scrobble

Once the user picks a release number N, run:

```
SCROBBLE_CLI_PATH/scrobble-wrapper.sh album <query> --pick N -y
```

This selects release N and skips the confirmation prompt.

## Flag passthrough

Pass through any of these flags from `$ARGUMENTS` if present:
- `--dry-run` — print what would be scrobbled without calling Last.fm
- `--allow-ignored` — exit 0 even if Last.fm ignores some tracks
- `--started-at "ISO_TIMESTAMP"` — override when listening started
- `--ended-at "ISO_TIMESTAMP"` — override when listening ended
- `--any-format` — don't prefer vinyl matches on Discogs
- `--no-auto` — disable auto-pick even when extremely confident

These flags apply to both the `--search-only` step and the `--pick N -y` step.

## Examples

User says: `/scrobble miles davis kind of blue`
1. Run: `scrobble-wrapper.sh album miles davis kind of blue --search-only`
2. Show results, ask user to pick
3. Run: `scrobble-wrapper.sh album miles davis kind of blue --pick 3 -y`

User says: `/scrobble ended barney wilen moshi --dry-run`
1. Run: `scrobble-wrapper.sh album ended barney wilen moshi --search-only --dry-run`
2. Show results, ask user to pick
3. Run: `scrobble-wrapper.sh album ended barney wilen moshi --pick 1 -y --dry-run`

## Notes

- The CLI has interactive TUI elements (questionary) that don't work in Claude Code's Bash tool. Always use `--search-only` + `--pick N -y` for the non-interactive flow.
- Auth tokens for Discogs and Last.fm are stored locally. If auth fails, tell the user to run `scrobble auth discogs` and `scrobble auth lastfm` manually in their terminal.
