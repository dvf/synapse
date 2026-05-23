from datetime import UTC, datetime, timedelta

import pytest

from synapse_p2p.schedules import cron, every, solar


def test_every_returns_next_interval():
    schedule = every(minutes=5)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)

    assert schedule.next_after(now) == now + timedelta(minutes=5)


def test_cron_returns_next_matching_datetime():
    schedule = cron("*/15 * * * *", tz="UTC")
    now = datetime(2026, 1, 1, 12, 1, tzinfo=UTC)

    assert schedule.next_after(now) == datetime(2026, 1, 1, 12, 15, tzinfo=UTC)


def test_solar_supports_civil_twilight():
    schedule = solar("civil_twilight_begin", latitude=51.5, longitude=-0.1, tz="UTC")
    now = datetime(2026, 6, 1, 0, 0, tzinfo=UTC)

    next_run = schedule.next_after(now)

    assert next_run.tzinfo is not None
    assert next_run.date() == now.date()
    assert 2 <= next_run.hour <= 4


def test_solar_rejects_unknown_event():
    schedule = solar("not_real", latitude=51.5, longitude=-0.1, tz="UTC")

    with pytest.raises(ValueError, match="unknown solar event"):
        schedule.next_after(datetime(2026, 1, 1, tzinfo=UTC))
