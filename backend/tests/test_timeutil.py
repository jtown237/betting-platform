# backend/tests/test_timeutil.py
"""Tests for UTC timestamp serialisation.

The DateTime columns are naive and hold UTC. Serialising them with no offset
made JavaScript's Date parser read them as the viewer's local time; a client
that then formatted in UTC applied the offset twice and displayed a kickoff
about two offsets away from the truth.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.timeutil import utc_iso


class TestUtcIso:
    def test_naive_is_treated_as_utc_and_marked(self):
        assert utc_iso(datetime(2026, 9, 3, 23, 15, 0)) == "2026-09-03T23:15:00+00:00"

    def test_aware_utc_keeps_its_instant(self):
        value = datetime(2026, 9, 3, 23, 15, 0, tzinfo=timezone.utc)
        assert utc_iso(value) == "2026-09-03T23:15:00+00:00"

    def test_other_offsets_are_converted_to_utc(self):
        central = timezone(timedelta(hours=-5))
        value = datetime(2026, 9, 3, 18, 15, 0, tzinfo=central)
        assert utc_iso(value) == "2026-09-03T23:15:00+00:00"

    def test_none_passes_through(self):
        assert utc_iso(None) is None

    @pytest.mark.parametrize(
        "value",
        [
            datetime(2026, 9, 3, 23, 15, 0),
            datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        ],
    )
    def test_output_always_states_a_zone(self, value):
        rendered = utc_iso(value)
        assert rendered.endswith("+00:00"), (
            f"{rendered} has no offset; JavaScript would parse it as local time"
        )
        # And it must round-trip back to the same instant.
        assert datetime.fromisoformat(rendered) == value.replace(
            tzinfo=value.tzinfo or timezone.utc
        )
