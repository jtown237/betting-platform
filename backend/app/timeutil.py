# backend/app/timeutil.py
"""Timestamp serialisation helpers."""

from datetime import datetime, timezone
from typing import Optional


def utc_iso(value: Optional[datetime]) -> Optional[str]:
    """
    Serialise a stored timestamp as unambiguous UTC.

    The DateTime columns are naive and hold UTC. Emitting them with no offset
    makes JavaScript's Date parser treat them as the viewer's *local* time, so
    a client that then formats in UTC applies the offset twice and lands
    roughly two offsets away from the real kickoff. Always state the zone.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()
