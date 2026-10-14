from __future__ import annotations
from datetime import datetime, time as dt_time, date as dt_date, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator, model_validator
from zoneinfo import ZoneInfo
import re

WILDCARD = "*"
MAX_RADIUS_KM = 5.0
MIN_RADIUS_KM = 0.1


class MatcherVersion(str, Enum):
    LEGACY_V1 = "legacy_v1"
    GLOB_V2 = "glob_v2"


def pattern_matches(pattern: str, candidate: str, version: MatcherVersion) -> bool:
    if version == MatcherVersion.LEGACY_V1:
        return pattern == WILDCARD or pattern.casefold() == candidate.casefold()
    expression = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
    return re.match(expression, candidate, re.IGNORECASE) is not None


class ValueObject(BaseModel):
    model_config = ConfigDict(frozen=True)


class GeoPoint(ValueObject):
    lat: float
    lng: float

    @field_validator("lat")
    @classmethod
    def latitude(cls, value: float) -> float:
        if not -90 <= value <= 90:
            raise ValueError("latitude must be between -90 and 90")
        return value

    @field_validator("lng")
    @classmethod
    def longitude(cls, value: float) -> float:
        if not -180 <= value <= 180:
            raise ValueError("longitude must be between -180 and 180")
        return value


class Subject(ValueObject):
    value: str

    def matches(self, candidate: str, version: MatcherVersion = MatcherVersion.LEGACY_V1) -> bool:
        return pattern_matches(self.value, candidate, version)


class Resource(ValueObject):
    value: str

    def matches(self, candidate: str, version: MatcherVersion = MatcherVersion.LEGACY_V1) -> bool:
        return pattern_matches(self.value, candidate, version)


class Location(ValueObject):
    """center=None is a wildcard that matches any location.
    Distance is computed via the Haversine/geodesic formula (geopy).
    """
    center:    Optional[GeoPoint] = None
    radius_km: float = 1.0

    @field_validator("radius_km")
    @classmethod
    def radius(cls, value: float) -> float:
        if not MIN_RADIUS_KM <= value <= MAX_RADIUS_KM:
            raise ValueError(f"radius_km must be between {MIN_RADIUS_KM} and {MAX_RADIUS_KM}")
        return value

    def matches(self, candidate: Optional[GeoPoint]) -> bool:
        if self.center is None or candidate is None:
            return True
        from geopy.distance import geodesic
        dist = geodesic(
            (self.center.lat, self.center.lng),
            (candidate.lat,  candidate.lng),
        ).km
        return dist <= self.radius_km


class Action(ValueObject):
    value: str

    def matches(self, candidate: str, version: MatcherVersion = MatcherVersion.LEGACY_V1) -> bool:
        return pattern_matches(self.value, candidate, version)


class TimeWindowMode(str, Enum):
    WILDCARD    = "wildcard"
    DATETIME    = "datetime"
    TIME_OF_DAY = "time_of_day"
    DATE        = "date"


class TimeWindow(ValueObject):
    mode:  TimeWindowMode = TimeWindowMode.WILDCARD
    start: Optional[str]  = None
    end:   Optional[str]  = None

    @property
    def is_wildcard(self) -> bool:
        return self.mode == TimeWindowMode.WILDCARD

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.mode == TimeWindowMode.WILDCARD:
            if self.start is not None or self.end is not None:
                raise ValueError("wildcard time windows cannot define bounds")
            return self
        if self.start is None or self.end is None:
            raise ValueError(f"{self.mode.value} time windows require start and end")
        try:
            if self.mode == TimeWindowMode.DATETIME:
                start, end = datetime.fromisoformat(self.start), datetime.fromisoformat(self.end)
                if start > end:
                    raise ValueError("datetime start must not be after end")
            elif self.mode == TimeWindowMode.TIME_OF_DAY:
                dt_time.fromisoformat(self.start)
                dt_time.fromisoformat(self.end)
            else:
                start, end = dt_date.fromisoformat(self.start), dt_date.fromisoformat(self.end)
                if start > end:
                    raise ValueError("date start must not be after end")
        except ValueError as exc:
            raise ValueError(f"invalid {self.mode.value} interval: {exc}") from exc
        return self

    def matches(self, candidate: Optional[str], policy_timezone: str = "UTC") -> bool:
        # None request time = wildcard pass (time not declared by requester)
        if candidate is None or self.mode == TimeWindowMode.WILDCARD:
            return True
        try:
            parsed_candidate = datetime.fromisoformat(
                candidate[:-1] + "+00:00" if candidate.endswith(("Z", "z")) else candidate
            )
            if parsed_candidate.tzinfo is None:
                parsed_candidate = parsed_candidate.replace(tzinfo=timezone.utc)
            local_candidate = parsed_candidate.astimezone(ZoneInfo(policy_timezone))
            if self.mode == TimeWindowMode.DATETIME:
                start = datetime.fromisoformat(self.start)
                end = datetime.fromisoformat(self.end)
                if start.tzinfo is None:
                    start = start.replace(tzinfo=ZoneInfo(policy_timezone))
                if end.tzinfo is None:
                    end = end.replace(tzinfo=ZoneInfo(policy_timezone))
                return (
                    start <= local_candidate <= end
                )

            if self.mode == TimeWindowMode.TIME_OF_DAY:
                s = dt_time.fromisoformat(self.start)
                e = dt_time.fromisoformat(self.end)
                c = local_candidate.time().replace(tzinfo=None)
                if s <= e:
                    return s <= c <= e
                # Midnight-spanning window (e.g. 22:00 → 06:00):
                # match if candidate is in the evening part OR the morning part.
                return c >= s or c <= e

            if self.mode == TimeWindowMode.DATE:
                s = dt_date.fromisoformat(self.start)
                e = dt_date.fromisoformat(self.end)
                c = local_candidate.date()
                return s <= c <= e

        except (ValueError, AttributeError):
            return False

        return False


class Effect(str, Enum):
    ALLOW = "ALLOW"
    DENY  = "DENY"
