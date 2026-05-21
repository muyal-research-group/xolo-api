from typing import List, Optional
from pydantic import BaseModel, field_validator
from xoloapi.abac.domain.value_objects import Effect, MAX_RADIUS_KM, TimeWindowMode


class GeoPointDTO(BaseModel):
    lat: float
    lng: float


class GeoZoneDTO(BaseModel):
    lat:       float
    lng:       float
    radius_km: float = 1.0

    @field_validator("radius_km")
    @classmethod
    def cap_radius(cls, v: float) -> float:
        if v <= 0 or v > MAX_RADIUS_KM:
            raise ValueError(f"radius_km must be between 0 and {MAX_RADIUS_KM}")
        return v


class CreateABACEventDTO(BaseModel):
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


class ABACEvaluateDTO(BaseModel):
    subject:  str
    resource: str
    location: Optional[GeoPointDTO] = None         # None = anywhere (wildcard pass)
    time:     Optional[str]         = None         # "YYYY-MM-DDTHH:MM" or None
    action:   str


class ABACDecisionDTO(BaseModel):
    allowed:        bool
    matched_policy: Optional[str] = None
    matched_event:  Optional[str] = None
    reason:         str


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
