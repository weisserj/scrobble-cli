# Scrobble an album to Last.fm

Scrobble a vinyl record to Last.fm by looking up its tracklist on Discogs.

## Arguments

$ARGUMENTS is the album query (e.g. "miles davis kind of blue"). It may optionally be prefixed with "ended" to indicate the album just finished playing.

## Instructions

1. **Search Discogs** for the album:
   ```bash
   scrobble album $ARGUMENTS --search-only
   ```
   This returns a JSON array of matching releases.

2. **Pick the correct release:**
   - If there's an obvious match (correct artist, album, and format), note its number.
   - If the results are ambiguous, present the options to the user as a numbered list (include title, year, format, label) and ask them to pick one.

3. **Scrobble** the selected release:
   ```bash
   scrobble album $ARGUMENTS --pick <NUMBER> -y
   ```
   Use the number from step 2. The `-y` flag skips the confirmation prompt.

4. **Report the result** to the user: which album was scrobbled, how many tracks, and whether any tracks were ignored by Last.fm.

## Notes

- If the user says "ended" or "just finished", prefix the query with `ended` so timestamps count backward from now.
- Add `--dry-run` if the user asks to preview without actually scrobbling.
- Add `--any-format` if the user wants non-vinyl results.
- If `--search-only` returns no results, try broadening the query (e.g. drop extra words).
