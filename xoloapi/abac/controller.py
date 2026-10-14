import time as T
from nanoid import generate
from zoneinfo import available_timezones
from fastapi import APIRouter, Depends, Response, status
from xoloapi.log import Log

import xoloapi.config as Cfg
import xoloapi.db as DbX
import xoloapi.middleware as MX
import commonx.dto.xolo as DTO

from xoloapi.accounts.dependencies import require_existing_account
from xoloapi.accounts.dependencies import get_accounts_service
from xoloapi.accounts.application.accounts_service import AccountsService
from xoloapi.middleware.apikey import require_api_key
from xoloapi.abac.application.abac_service import ABACService
from xoloapi.abac.domain.aggregates import ABACAccessRequest, ABACEvent
from xoloapi.abac.domain.value_objects import Action, GeoPoint, Location, Resource, Subject, TimeWindow
from xoloapi.abac.dto import (
    ABACDecisionDTO, ABACEvaluateDTO, ABACEventResponseDTO, ABACLocationResponseDTO,
    ABACPolicyResponseDTO, ABACTimeWindowResponseDTO, ABACValueDTO,
    CreateABACPolicyDTO, GeoPointDTO,
)
from xoloapi.abac.infrastructure.mongo_abac_repository import MongoABACRepository
from xoloapi.db.constants import CollectionNames
from xoloapi.log.format import build_log_payload

log = Log(
    name                   = __name__,
    console_handler_filter = lambda x: True,
    interval               = Cfg.XOLO_LOG_INTERVAL,
    when                   = Cfg.XOLO_LOG_WHEN,
    path                   = Cfg.XOLO_LOG_PATH,
)

router = APIRouter(
    prefix="/accounts/{account_id}/abac",
    tags=["abac"],
    dependencies=[Depends(require_existing_account)],
)


# ── Dependency factory ────────────────────────────────────────────────────────

def get_abac_service() -> ABACService:
    return ABACService(
        repository=MongoABACRepository(
            db              = DbX.get_database(),
            collection_name = CollectionNames.ABAC_POLICIES_COLLECTION_NAME,
        )
    )


def _policy_to_dto(policy) -> ABACPolicyResponseDTO:
    return ABACPolicyResponseDTO(
        policy_id = policy.policy_id,
        name      = policy.name,
        effect    = policy.effect,
        events    = [
            ABACEventResponseDTO(
                event_id = e.event_id,
                subject  = ABACValueDTO(value=e.subject.value),
                resource = ABACValueDTO(value=e.resource.value),
                location = ABACLocationResponseDTO(
                    center    = GeoPointDTO(lat=e.location.center.lat, lng=e.location.center.lng) if e.location.center else None,
                    radius_km = e.location.radius_km,
                ),
                time   = ABACTimeWindowResponseDTO(mode=e.time.mode, start=e.time.start, end=e.time.end),
                action = ABACValueDTO(value=e.action.value),
            )
            for e in policy.events
        ],
        matcher_version = policy.matcher_version,
        timezone = policy.timezone,
        created_at = policy.created_at,
        updated_at = policy.updated_at,
    )


def _events_from_dto(dto: CreateABACPolicyDTO, existing: list[ABACEvent] | None = None) -> list[ABACEvent]:
    return [
        ABACEvent(
            event_id = ev.event_id or (existing[index].event_id if existing and index < len(existing) else f"ev-{generate(size=8)}"),
            subject  = Subject(value=ev.subject),
            resource = Resource(value=ev.resource),
            location = Location(
                center    = GeoPoint(lat=ev.location.lat, lng=ev.location.lng) if ev.location else None,
                radius_km = ev.location.radius_km if ev.location else 1.0,
            ),
            time     = TimeWindow(mode=ev.time_mode, start=ev.time_start, end=ev.time_end),
            action   = Action(value=ev.action),
        )
        for index, ev in enumerate(dto.events)
    ]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/timezones")
async def timezones(
    account_id: str,
    _: object = Depends(require_api_key("abac")),
    accounts: AccountsService = Depends(get_accounts_service),
):
    account = await accounts.get_account(account_id)
    if account.is_err:
        raise account.unwrap_err().to_http_exception()
    default = account.unwrap().timezone
    return {"default": default, "timezones": sorted(available_timezones())}

@router.post("/policies", status_code=status.HTTP_201_CREATED)
async def create_policy(
    account_id: str,
    dto:     CreateABACPolicyDTO,
    _:       object      = Depends(require_api_key("abac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: ABACService = Depends(get_abac_service),
    accounts: AccountsService = Depends(get_accounts_service),
):
    t1     = T.time()
    events = _events_from_dto(dto)
    account = await accounts.get_account(account_id)
    if account.is_err:
        raise account.unwrap_err().to_http_exception()
    result = await service.create_policy(account_id, dto.name, dto.effect, events, dto.timezone or account.unwrap().timezone)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("abac.create_policy.error", started_at=t1, error=err, actor_user_id=me.key, policy_name=dto.name))
        raise err.to_http_exception()
    policy_id = result.unwrap()
    log.info(build_log_payload("abac.create_policy", started_at=t1, actor_user_id=me.key, policy_id=policy_id, policy_name=dto.name))
    return {"policy_id": policy_id}


@router.get("/policies", status_code=status.HTTP_200_OK)
async def list_policies(
    account_id: str,
    _:       object      = Depends(require_api_key("abac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: ABACService = Depends(get_abac_service),
):
    t1     = T.time()
    result = await service.list_policies(account_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("abac.list_policies.error", started_at=t1, error=err, actor_user_id=me.key))
        raise err.to_http_exception()
    policies = result.unwrap()
    log.info(build_log_payload("abac.list_policies", started_at=t1, actor_user_id=me.key, policy_count=len(policies)))
    return [_policy_to_dto(p) for p in policies]


@router.get("/policies/list", status_code=status.HTTP_200_OK)
async def list_policies_discovery(
    account_id: str,
    _:       object      = Depends(require_api_key("abac")),
    service: ABACService = Depends(get_abac_service),
):
    t1     = T.time()
    result = await service.list_policies(account_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("abac.list_policies_discovery.error", started_at=t1, error=err))
        raise err.to_http_exception()
    policies = result.unwrap()
    log.info(build_log_payload("abac.list_policies_discovery", started_at=t1, policy_count=len(policies)))
    return [{"id": p.policy_id, "name": p.name} for p in policies]


@router.get("/policies/{policy_id}", status_code=status.HTTP_200_OK)
async def get_policy(
    account_id: str,
    policy_id: str,
    _:         object      = Depends(require_api_key("abac")),
    me:        DTO.UserDTO = Depends(MX.get_current_user),
    service:   ABACService = Depends(get_abac_service),
):
    t1     = T.time()
    result = await service.get_policy(account_id, policy_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("abac.get_policy.error", started_at=t1, error=err, actor_user_id=me.key, policy_id=policy_id))
        raise err.to_http_exception()
    log.info(build_log_payload("abac.get_policy", started_at=t1, actor_user_id=me.key, policy_id=policy_id))
    return _policy_to_dto(result.unwrap())


@router.put("/policies/{policy_id}", status_code=status.HTTP_200_OK)
async def update_policy(
    account_id: str,
    policy_id: str,
    dto:       CreateABACPolicyDTO,
    _:         object      = Depends(require_api_key("abac")),
    me:        DTO.UserDTO = Depends(MX.get_current_user),
    service:   ABACService = Depends(get_abac_service),
):
    t1 = T.time()
    existing = await service.get_policy(account_id, policy_id)
    if existing.is_err:
        raise existing.unwrap_err().to_http_exception()
    result = await service.update_policy(
        account_id,
        policy_id,
        dto.name,
        dto.effect,
        _events_from_dto(dto, existing.unwrap().events),
        dto.timezone,
    )
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("abac.update_policy.error", started_at=t1, error=err, actor_user_id=me.key, policy_id=policy_id))
        raise err.to_http_exception()

    updated = await service.get_policy(account_id, policy_id)
    if updated.is_err:
        err = updated.unwrap_err()
        raise err.to_http_exception()
    log.info(build_log_payload("abac.update_policy", started_at=t1, actor_user_id=me.key, policy_id=policy_id))
    return _policy_to_dto(updated.unwrap())


@router.post("/policies/{policy_id}/upgrade-matcher", status_code=status.HTTP_200_OK)
async def upgrade_matcher(
    account_id: str,
    policy_id: str,
    _: object = Depends(require_api_key("abac")),
    me: DTO.UserDTO = Depends(MX.get_current_user),
    service: ABACService = Depends(get_abac_service),
):
    result = await service.upgrade_matcher(account_id, policy_id)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    updated = await service.get_policy(account_id, policy_id)
    return _policy_to_dto(updated.unwrap())


@router.delete("/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    account_id: str,
    policy_id: str,
    _:         object      = Depends(require_api_key("abac")),
    me:        DTO.UserDTO = Depends(MX.get_current_user),
    service:   ABACService = Depends(get_abac_service),
):
    t1     = T.time()
    result = await service.delete_policy(account_id, policy_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("abac.delete_policy.error", started_at=t1, error=err, actor_user_id=me.key, policy_id=policy_id))
        raise err.to_http_exception()
    log.info(build_log_payload("abac.delete_policy", started_at=t1, actor_user_id=me.key, policy_id=policy_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/evaluate", status_code=status.HTTP_200_OK)
async def evaluate(
    account_id: str,
    dto:     ABACEvaluateDTO,
    _:       object      = Depends(require_api_key("abac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: ABACService = Depends(get_abac_service),
):
    t1      = T.time()
    request = ABACAccessRequest(
        subject  = dto.subject,
        resource = dto.resource,
        location = GeoPoint(lat=dto.location.lat, lng=dto.location.lng) if dto.location else None,
        time     = dto.time,
        action   = dto.action,
    )
    result = await service.evaluate(account_id, request)
    if result.is_err:
        err = result.unwrap_err()
        log.error(
            build_log_payload(
                "abac.evaluate.error",
                started_at=t1,
                error=err,
                actor_user_id=me.key,
                subject=dto.subject,
                resource=dto.resource,
                location=dto.location,
                action_name=dto.action,
            )
        )
        raise err.to_http_exception()
    decision = result.unwrap()
    log.info(
        build_log_payload(
            "abac.evaluate",
            started_at=t1,
            actor_user_id=me.key,
            subject=dto.subject,
            resource=dto.resource,
            location=dto.location,
            action_name=dto.action,
            allowed=decision.allowed,
            matched_policy=decision.matched_policy,
            matched_event=decision.matched_event,
        )
    )
    return ABACDecisionDTO(
        allowed        = decision.allowed,
        matched_policy = decision.matched_policy,
        matched_event  = decision.matched_event,
        reason         = decision.reason,
        matched_policy_ids = decision.matched_policy_ids,
        matched_event_ids = decision.matched_event_ids,
        request_context = decision.request_context,
        warnings = decision.warnings,
    )


# ── Data Discovery Endpoints ──────────────────────────────────────────────────

@router.get("/subjects/list", status_code=status.HTTP_200_OK)
async def list_subjects_discovery(
    account_id: str,
    _:       object      = Depends(require_api_key("abac")),
):
    t1 = T.time()
    # Return placeholder subjects for now - can be extended
    subjects = []
    log.info(build_log_payload("abac.list_subjects_discovery", started_at=t1, subject_count=len(subjects)))
    return subjects


@router.get("/resources/list", status_code=status.HTTP_200_OK)
async def list_abac_resources_discovery(
    account_id: str,
    _:       object      = Depends(require_api_key("abac")),
):
    t1 = T.time()
    # Return placeholder resources for now - can be extended
    resources = []
    log.info(build_log_payload("abac.list_resources_discovery", started_at=t1, resource_count=len(resources)))
    return resources


@router.get("/locations/list", status_code=status.HTTP_200_OK)
async def list_locations_discovery(
    account_id: str,
    _:       object      = Depends(require_api_key("abac")),
):
    t1 = T.time()
    # Return placeholder locations for now - can be extended
    locations = []
    log.info(build_log_payload("abac.list_locations_discovery", started_at=t1, location_count=len(locations)))
    return locations
