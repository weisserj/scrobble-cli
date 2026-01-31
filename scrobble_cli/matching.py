from __future__ import annotations

import re


def _norm(s: str) -> str:
  s = (s or "").strip().lower()
  s = re.sub(r"\s+", " ", s)
  s = re.sub(r"[^a-z0-9 &/+'-]", "", s)
  return s


def discogs_title_confidence(*, artist: str, album: str, discogs_title: str) -> float:
  want_artist = _norm(artist)
  want_album = _norm(album)
  title = _norm(discogs_title)

  if " - " in title:
    got_artist, got_album = title.split(" - ", 1)
  else:
    got_artist, got_album = title, title

  if got_artist == want_artist and got_album == want_album:
    return 1.0
  if got_album == want_album and (got_artist.startswith(want_artist) or want_artist.startswith(got_artist)):
    return 0.92

  want_tokens = set((want_artist + " " + want_album).split())
  got_tokens = set(title.split())
  if not want_tokens or not got_tokens:
    return 0.0
  overlap = len(want_tokens & got_tokens) / len(want_tokens)
  return min(0.8, overlap)


def discogs_query_confidence(*, query: str, discogs_title: str) -> float:
  want = _norm(query)
  got = _norm(discogs_title)
  want_tokens = set(want.split())
  got_tokens = set(got.split())
  if not want_tokens or not got_tokens:
    return 0.0
  overlap = len(want_tokens & got_tokens) / len(want_tokens)
  if overlap >= 0.95:
    return 0.92
  return min(0.8, overlap)

