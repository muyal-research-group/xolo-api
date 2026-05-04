import time as T
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Body
from xolo.log import Log
from xolo.abac.models import Policy, AccessRequest
from xolo.abac.graph import GraphBuilder
from xolo.abac.communities import CommunityDetector
from xolo.abac.evaluator import CommunityPolicyEvaluator

import xoloapi.config as Cfg
import xoloapi.middleware as MX
import commonx.dto.xolo as DTO

from xoloapi.logging import build_log_payload
from xoloapi.middleware.apikey import require_api_key
from xoloapi.policies.repository import PoliciesRepository
from xoloapi.policies.service import PolicyService

log = Log(
    name                   = __name__,
    console_handler_filter = lambda x: True,
    interval               = Cfg.XOLO_LOG_INTERVAL,
    when                   = Cfg.XOLO_LOG_WHEN,
    path                   = Cfg.XOLO_LOG_PATH,
)

router = APIRouter(prefix="/policies", tags=["policies"])


# ── Module-level singletons (in-memory state must survive requests) ───────────

_repo    = PoliciesRepository()
_service = PolicyService(
    repository         = _repo,
    graph_builder      = GraphBuilder(),
    community_detector = CommunityDetector(),
    evaluator          = CommunityPolicyEvaluator(),
)


def get_repo() -> PoliciesRepository:
    return _repo


def get_service() -> PolicyService:
    return _service


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
def create_policy(
    policies: List[Policy],
    _:        object            = Depends(require_api_key("policies")),
    me:       DTO.UserDTO       = Depends(MX.get_current_user),
    repo:     PoliciesRepository = Depends(get_repo),
):
    t1  = T.time()
    res = repo.create_policies(policies)
    if res.is_err:
        log.error(build_log_payload("policies.create.error", started_at=t1, error=res.unwrap_err(), actor_user_id=me.key, policy_count=len(policies)))
        raise HTTPException(status_code=500, detail="Failed to create policy")
    n = res.unwrap()
    log.info(build_log_payload("policies.create", started_at=t1, actor_user_id=me.key, requested_policy_count=len(policies), added_policy_count=n))
    return {"n_added": n}


@router.get("", status_code=status.HTTP_200_OK)
def list_policies(
    _:    object            = Depends(require_api_key("policies")),
    me:   DTO.UserDTO       = Depends(MX.get_current_user),
    repo: PoliciesRepository = Depends(get_repo),
):
    t1 = T.time()
    res = repo.list_policies()
    if res.is_err:
        log.error(build_log_payload("policies.list.error", started_at=t1, error=res.unwrap_err(), actor_user_id=me.key))
        raise HTTPException(status_code=500, detail="Failed to get policies")
    policies = res.unwrap()
    log.info(build_log_payload("policies.list", started_at=t1, actor_user_id=me.key, policy_count=len(policies)))
    return policies


@router.get("/{policy_id}", status_code=status.HTTP_200_OK)
def get_policy(
    policy_id: str,
    _:         object            = Depends(require_api_key("policies")),
    me:        DTO.UserDTO       = Depends(MX.get_current_user),
    repo:      PoliciesRepository = Depends(get_repo),
):
    t1 = T.time()
    res = repo.get_policy(policy_id)
    if res.is_err:
        log.warning(build_log_payload("policies.get.error", started_at=t1, error=res.unwrap_err(), actor_user_id=me.key, policy_id=policy_id))
        raise HTTPException(status_code=404, detail="Policy not found")
    log.info(build_log_payload("policies.get", started_at=t1, actor_user_id=me.key, policy_id=policy_id))
    return res.unwrap()


@router.delete("/{policy_id}", status_code=status.HTTP_200_OK)
def delete_policy(
    policy_id: str,
    _:         object            = Depends(require_api_key("policies")),
    me:        DTO.UserDTO       = Depends(MX.get_current_user),
    repo:      PoliciesRepository = Depends(get_repo),
    service:   PolicyService      = Depends(get_service),
):
    t1 = T.time()
    result = repo.delete_policy(policy_id)
    if result.is_err or not result.unwrap_or(False):
        log.warning(build_log_payload("policies.delete.error", started_at=t1, error=result.unwrap_err() if result.is_err else Exception("Policy not found"), actor_user_id=me.key, policy_id=policy_id))
        raise HTTPException(status_code=404, detail="Policy not found")
    service.evaluator.remove_policy(policy_id)
    log.info(build_log_payload("policies.delete", started_at=t1, actor_user_id=me.key, policy_id=policy_id))
    return {"detail": "Policy deleted"}


@router.put("/{policy_id}", status_code=status.HTTP_200_OK)
def update_policy(
    policy_id:      str,
    updated_policy: Policy,
    _:              object       = Depends(require_api_key("policies")),
    me:             DTO.UserDTO  = Depends(MX.get_current_user),
    service:        PolicyService = Depends(get_service),
):
    t1  = T.time()
    res = service.update_policy(policy_id, updated_policy)
    if res.is_err:
        log.error(build_log_payload("policies.update.error", started_at=t1, error=res.unwrap_err(), actor_user_id=me.key, policy_id=policy_id))
        raise HTTPException(status_code=500, detail="Failed to update policy")
    log.info(build_log_payload("policies.update", started_at=t1, actor_user_id=me.key, policy_id=policy_id))
    return {"detail": "Policy updated"}


@router.post("/prepare", status_code=status.HTTP_200_OK)
def prepare_communities(
    _:       object       = Depends(require_api_key("policies")),
    me:      DTO.UserDTO  = Depends(MX.get_current_user),
    service: PolicyService = Depends(get_service),
):
    t1  = T.time()
    res = service.prepare_communities()
    if res.is_err:
        log.error(build_log_payload("policies.prepare.error", started_at=t1, error=res.unwrap_err(), actor_user_id=me.key))
        raise HTTPException(status_code=500, detail="Failed to prepare communities")
    communities = res.unwrap()
    log.info(build_log_payload("policies.prepare", started_at=t1, actor_user_id=me.key, community_count=len(communities)))
    return communities


@router.post("/evaluate", status_code=status.HTTP_200_OK)
def evaluate_request(
    req:     AccessRequest,
    _:       object       = Depends(require_api_key("policies")),
    me:      DTO.UserDTO  = Depends(MX.get_current_user),
    service: PolicyService = Depends(get_service),
):
    t1  = T.time()
    res = service.evaluate_request(req)
    if res.is_err:
        log.error(build_log_payload("policies.evaluate.error", started_at=t1, error=res.unwrap_err(), actor_user_id=me.key))
        raise HTTPException(status_code=500, detail="Failed to evaluate request")
    result = res.unwrap()
    log.info(build_log_payload("policies.evaluate", started_at=t1, actor_user_id=me.key))
    return result


@router.post("/evaluate/batch", status_code=status.HTTP_200_OK)
def evaluate_batch(
    requests: List[AccessRequest] = Body(...),
    _:        object              = Depends(require_api_key("policies")),
    me:       DTO.UserDTO         = Depends(MX.get_current_user),
    service:  PolicyService        = Depends(get_service),
):
    t1      = T.time()
    results = []
    for req in requests:
        res = service.evaluate_request(req)
        if res.is_ok:
            results.append(res.unwrap())
        else:
            results.append({"result": "error", "error": str(res.unwrap_err())})
    log.info(build_log_payload("policies.evaluate_batch", started_at=t1, actor_user_id=me.key, request_count=len(requests)))
    return results


@router.post("/inject", status_code=status.HTTP_200_OK)
def inject_policy(
    policy:  Policy,
    _:       object       = Depends(require_api_key("policies")),
    me:      DTO.UserDTO  = Depends(MX.get_current_user),
    service: PolicyService = Depends(get_service),
):
    t1 = T.time()
    if not service.evaluator.policies_by_community:
        log.warning(build_log_payload("policies.inject.error", started_at=t1, actor_user_id=me.key, policy_id=policy.policy_id))
        raise HTTPException(
            status_code=400,
            detail="Communities must be prepared before injecting policies",
        )
    res = service.create_policy_incremental(policy)
    if res.is_err:
        log.error(build_log_payload("policies.inject.error", started_at=t1, error=res.unwrap_err(), actor_user_id=me.key, policy_id=policy.policy_id))
        raise HTTPException(status_code=500, detail="Failed to inject policy")
    log.info(build_log_payload("policies.inject", started_at=t1, actor_user_id=me.key, policy_id=policy.policy_id))
    return {"detail": "Policy injected"}
