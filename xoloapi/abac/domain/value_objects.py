from __future__ import annotations
from datetime import datetime, time as dt_time, date as dt_date
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict

WILDCARD = "*"
MAX_RADIUS_KM = 5.0


class ValueObject(BaseModel):
    model_config = ConfigDict(frozen=True)


class GeoPoint(ValueObject):
    lat: float
    lng: float


class Subject(ValueObject):
    value: str

    def matches(self, candidate: str) -> bool:
        return self.value == WILDCARD or self.value.lower() == candidate.lower()


class Resource(ValueObject):
    value: str

    def matches(self, candidate: str) -> bool:
        return self.value == WILDCARD or self.value.lower() == candidate.lower()


class Location(ValueObject):
    """center=None is a wildcard that matches any location.
    Distance is computed via the Haversine/geodesic formula (geopy).
    """
    center:    Optional[GeoPoint] = None
    radius_km: float = 1.0

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

    def matches(self, candidate: str) -> bool:
        return self.value == WILDCARD or self.value.upper() == candidate.upper()


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

    def matches(self, candidate: Optional[str]) -> bool:
        # None request time = wildcard pass (time not declared by requester)
        if candidate is None or self.mode == TimeWindowMode.WILDCARD:
            return True
        try:
            if self.mode == TimeWindowMode.DATETIME:
                return (
                    datetime.fromisoformat(self.start)
                    <= datetime.fromisoformat(candidate)
                    <= datetime.fromisoformat(self.end)
                )

            if self.mode == TimeWindowMode.TIME_OF_DAY:
                s = dt_time.fromisoformat(self.start)
                e = dt_time.fromisoformat(self.end)
                c = datetime.fromisoformat(candidate).time()
                if s <= e:
                    return s <= c <= e
                # Midnight-spanning window (e.g. 22:00 → 06:00):
                # match if candidate is in the evening part OR the morning part.
                return c >= s or c <= e

            if self.mode == TimeWindowMode.DATE:
                s = dt_date.fromisoformat(self.start)
                e = dt_date.fromisoformat(self.end)
                c = datetime.fromisoformat(candidate).date()
                return s <= c <= e

        except (ValueError, AttributeError):
            return False

        return False


class Effect(str, Enum):
    ALLOW = "ALLOW"
    DENY  = "DENY"
