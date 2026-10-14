from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, field_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from xoloapi.abac.domain.value_objects import Effect, MatcherVersion, MAX_RADIUS_KM, MIN_RADIUS_KM, TimeWindowMode


class GeoPointDTO(BaseModel):
    lat: float
    lng: float

    @field_validator("lat")
    @classmethod
    def lat_range(cls, value: float) -> float:
        if not -90 <= value <= 90:
            raise ValueError("lat must be between -90 and 90")
        return value

    @field_validator("lng")
    @classmethod
    def lng_range(cls, value: float) -> float:
        if not -180 <= value <= 180:
            raise ValueError("lng must be between -180 and 180")
        return value


class GeoZoneDTO(BaseModel):
    lat:       float
    lng:       float
    radius_km: float = 1.0

    @field_validator("radius_km")
    @classmethod
    def cap_radius(cls, v: float) -> float:
        if v < MIN_RADIUS_KM or v > MAX_RADIUS_KM:
            raise ValueError(f"radius_km must be between {MIN_RADIUS_KM} and {MAX_RADIUS_KM}")
        return v


class CreateABACEventDTO(BaseModel):
    event_id:   Optional[str] = None
    subject:    str
    resource:   str
    location:   Optional[GeoZoneDTO] = None        # None = wildcard
    time_mode:  TimeWindowMode = TimeWindowMode.WILDCARD
    time_start: Optional[str]  = None              # format depends on time_mode
    time_end:   Optional[str]  = None
    action:     str


class CreateABACPolicyDTO(BaseModel):
    name:   str
    effect: Effect = Effect.ALLOW
    events: List[CreateABACEventDTO]
    timezone: Optional[str] = None

    @field_validator("timezone")
    @classmethod
    def timezone_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA timezone") from exc
        return value


class ABACEvaluateDTO(BaseModel):
    subject:  str
    resource: str
    location: Optional[GeoPointDTO] = None         # None = anywhere (wildcard pass)
    time:     Optional[str]         = None         # "YYYY-MM-DDTHH:MM" or None
    action:   str

    @field_validator("time")
    @classmethod
    def aware_time(cls, value: str | None) -> str | None:
        if value is None:
            return None
        # Python 3.10 does not accept the otherwise standard ``Z`` suffix.
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("evaluation time must include a UTC offset or timezone")
        return value


class ABACDecisionDTO(BaseModel):
    allowed:        bool
    matched_policy: Optional[str] = None
    matched_event:  Optional[str] = None
    reason:         str
    matched_policy_ids: List[str] = []
    matched_event_ids: List[str] = []
    request_context: dict = {}
    warnings: List[str] = []


# ── Response DTOs ─────────────────────────────────────────────────────────────

class ABACValueDTO(BaseModel):
    value: str


class ABACLocationResponseDTO(BaseModel):
    center:    Optional[GeoPointDTO] = None
    radius_km: float = 1.0


class ABACTimeWindowResponseDTO(BaseModel):
    mode:  TimeWindowMode
    start: Optional[str] = None
    end:   Optional[str] = None


class ABACEventResponseDTO(BaseModel):
    event_id: str
    subject:  ABACValueDTO
    resource: ABACValueDTO
    location: ABACLocationResponseDTO
    time:     ABACTimeWindowResponseDTO
    action:   ABACValueDTO


class ABACPolicyResponseDTO(BaseModel):
    policy_id: str
    name:      str
    effect:    Effect
    events:    List[ABACEventResponseDTO]
    matcher_version: MatcherVersion
    timezone: str
    created_at: datetime
    updated_at: datetime
