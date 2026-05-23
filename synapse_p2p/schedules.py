from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo
from typing import Protocol
from zoneinfo import ZoneInfo

from astral import Depression, Observer
from astral.sun import dawn, dusk, noon, sunrise, sunset
from croniter import croniter


class Schedule(Protocol):
    def next_after(self, now: datetime) -> datetime:
        """Return the next scheduled run time after ``now``."""


def _coerce_tz(tz: str | tzinfo | None) -> tzinfo:
    if tz is None:
        return UTC
    if isinstance(tz, str):
        return ZoneInfo(tz)
    return tz


def _aware(now: datetime, tz: tzinfo) -> datetime:
    if now.tzinfo is None:
        return now.replace(tzinfo=tz)
    return now.astimezone(tz)


@dataclass(frozen=True, slots=True)
class IntervalSchedule:
    seconds: float

    def __post_init__(self) -> None:
        if self.seconds <= 0:
            raise ValueError("interval schedule must be greater than 0 seconds")

    def next_after(self, now: datetime) -> datetime:
        return now + timedelta(seconds=self.seconds)


@dataclass(frozen=True, slots=True)
class CronSchedule:
    expression: str
    tz: tzinfo = UTC
    day_or: bool = True

    def next_after(self, now: datetime) -> datetime:
        base = _aware(now, self.tz)
        return croniter(self.expression, base, day_or=self.day_or).get_next(datetime)


@dataclass(frozen=True, slots=True)
class SolarSchedule:
    event: str
    latitude: float
    longitude: float
    tz: tzinfo = UTC

    def next_after(self, now: datetime) -> datetime:
        base = _aware(now, self.tz)
        observer = Observer(latitude=self.latitude, longitude=self.longitude)
        day = base.date()

        for _ in range(370):
            candidate = self._event_time(observer, day)
            if candidate > base:
                return candidate
            day += timedelta(days=1)

        raise RuntimeError(f"could not find next solar event {self.event!r}")

    def _event_time(self, observer: Observer, day) -> datetime:
        match self.event:
            case "sunrise":
                return sunrise(observer, date=day, tzinfo=self.tz)
            case "sunset":
                return sunset(observer, date=day, tzinfo=self.tz)
            case "solar_noon" | "noon":
                return noon(observer, date=day, tzinfo=self.tz)
            case "civil_twilight_begin" | "civil_dawn" | "dawn":
                return dawn(observer, date=day, depression=Depression.CIVIL, tzinfo=self.tz)
            case "civil_twilight_end" | "civil_dusk" | "dusk":
                return dusk(observer, date=day, depression=Depression.CIVIL, tzinfo=self.tz)
            case "nautical_twilight_begin" | "nautical_dawn":
                return dawn(observer, date=day, depression=Depression.NAUTICAL, tzinfo=self.tz)
            case "nautical_twilight_end" | "nautical_dusk":
                return dusk(observer, date=day, depression=Depression.NAUTICAL, tzinfo=self.tz)
            case "astronomical_twilight_begin" | "astronomical_dawn":
                return dawn(observer, date=day, depression=Depression.ASTRONOMICAL, tzinfo=self.tz)
            case "astronomical_twilight_end" | "astronomical_dusk":
                return dusk(observer, date=day, depression=Depression.ASTRONOMICAL, tzinfo=self.tz)
            case _:
                raise ValueError(f"unknown solar event: {self.event}")


def every(
    *,
    seconds: float = 0,
    minutes: float = 0,
    hours: float = 0,
    days: float = 0,
) -> IntervalSchedule:
    total = seconds + minutes * 60 + hours * 3600 + days * 86400
    return IntervalSchedule(total)


def cron(expression: str, *, tz: str | tzinfo | None = None, day_or: bool = True) -> CronSchedule:
    return CronSchedule(expression=expression, tz=_coerce_tz(tz), day_or=day_or)


def solar(
    event: str,
    *,
    latitude: float,
    longitude: float,
    tz: str | tzinfo | None = None,
) -> SolarSchedule:
    return SolarSchedule(
        event=event,
        latitude=latitude,
        longitude=longitude,
        tz=_coerce_tz(tz),
    )
