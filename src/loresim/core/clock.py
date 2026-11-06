"""Story-world clock parser and formatter ("Day 3, 14:30" <-> total story minutes)."""

from __future__ import annotations

import re

_TIME_RE = re.compile(
    r"^\s*(?:Day\s*(\d+)\s*[,:\-]?\s*)?(\d{1,2}):(\d{2})\s*$",
    re.IGNORECASE,
)


def parse_story_time_to_minutes(time_str: str, fallback_tick: int = 0) -> int:
    """Convert 'Day D, HH:MM' or 'HH:MM' into total story minutes since Day 1, 00:00."""
    m = _TIME_RE.match(time_str)
    if not m:
        return fallback_tick * 30
    day = int(m.group(1)) if m.group(1) is not None else 1
    hour = int(m.group(2))
    minute = int(m.group(3))
    return max(0, (day - 1) * 1440 + hour * 60 + minute)


def format_minutes_to_story_time(total_minutes: int) -> str:
    """Format total story minutes since Day 1, 00:00 into 'Day D, HH:MM'."""
    mins = max(0, int(total_minutes))
    day = (mins // 1440) + 1
    rem = mins % 1440
    hour = rem // 60
    minute = rem % 60
    return f"Day {day}, {hour:02d}:{minute:02d}"
