from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TimestampPlan:
  started_at_unix: int
  ended_at_unix: int


def ensure_unix(dt: datetime) -> int:
  if dt.tzinfo is None:
    dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
  return int(dt.timestamp())


def plan_from_end(end_unix: int, durations: list[int]) -> list[int]:
  total = sum(durations)
  start = end_unix - total
  out = []
  t = start
  for d in durations:
    out.append(t)
    t += d
  return out


def plan_from_start(start_unix: int, durations: list[int]) -> list[int]:
  out = []
  t = start_unix
  for d in durations:
    out.append(t)
    t += d
  return out

