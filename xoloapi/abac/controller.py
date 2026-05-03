import time as T
from fastapi import APIRouter, Depends, Response, status
from xolo.log import Log

import xoloapi.config as Cfg
import xoloapi.db as DbX
import xoloapi.middleware as MX
import commonx.dto.xolo as DTO

from xoloapi.accounts.dependencies import require_existing_account
from xoloapi.middleware.apikey import require_api_key
from xoloapi.abac.application.abac_service import ABACService
from xoloapi.abac.dto import ABACEvaluateDTO, CreateABACPolicyDTO
from xoloapi.abac.infrastructure.mongo_abac_repository import MongoABACRepository
from xoloapi.db.constants import CollectionNames
from xoloapi.logging import build_log_payload

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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/policies", status_code=status.HTTP_201_CREATED)
async def create_policy(
    account_id: str,
    dto:     CreateABACPolicyDTO,
    _:       object      = Depends(require_api_key("abac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: ABACService = Depends(get_abac_service),
):
    t1     = T.time()
    result = await service.create_policy(account_id, dto)
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
    return [p.model_dump(exclude={"account_id"}) for p in policies]


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
    return result.unwrap().model_dump(exclude={"account_id"})


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
    t1     = T.time()
    result = await service.evaluate(account_id, dto)
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
    return decision.model_dump()
