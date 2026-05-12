import time as T
from fastapi import APIRouter, Depends, Query, Response, status
from xoloapi.log import Log

import xoloapi.config as Cfg
import xoloapi.db as DbX
import xoloapi.middleware as MX
import commonx.dto.xolo as DTO

from xoloapi.accounts.dependencies import require_existing_account
from xoloapi.acl.application.acl_service import ACLService
from xoloapi.acl.application.group_service import GroupService
from xoloapi.acl.domain.value_objects import PrincipalType
from xoloapi.acl.dto import CheckDTO, ClaimResourceDTO, GrantOrRevokeDTO, MembersDTO
from xoloapi.acl.infrastructure.mongo_resource_policy_repository import MongoResourcePolicyRepository
from xoloapi.acl.infrastructure.mongo_security_group_repository import MongoSecurityGroupRepository
from xoloapi.db.constants import CollectionNames
from xoloapi.logging import build_log_payload
from xoloapi.middleware.apikey import require_api_key

log = Log(
    name                   = __name__,
    console_handler_filter = lambda x: True,
    interval               = Cfg.XOLO_LOG_INTERVAL,
    when                   = Cfg.XOLO_LOG_WHEN,
    path                   = Cfg.XOLO_LOG_PATH,
)

router = APIRouter(
    prefix="/accounts/{account_id}/acl",
    tags=["acl"],
    dependencies=[Depends(require_existing_account)],
)


# ── Dependency factories ──────────────────────────────────────────────────────

def _group_repo() -> MongoSecurityGroupRepository:
    return MongoSecurityGroupRepository(
        db          = DbX.get_database(),
        groups_col  = CollectionNames.ACL_GROUPS_COLLECTION_NAME,
        members_col = CollectionNames.ACL_GROUP_MEMBERS_COLLECTION_NAME,
    )

def _policy_repo() -> MongoResourcePolicyRepository:
    return MongoResourcePolicyRepository(
        db              = DbX.get_database(),
        collection_name = CollectionNames.ACL_RESOURCE_POLICIES_COLLECTION_NAME,
    )

def get_acl_service(
    policy_repo: MongoResourcePolicyRepository = Depends(_policy_repo),
    group_repo:  MongoSecurityGroupRepository  = Depends(_group_repo),
) -> ACLService:
    return ACLService(policy_repo=policy_repo, group_repo=group_repo)

def get_group_service(
    group_repo: MongoSecurityGroupRepository = Depends(_group_repo),
) -> GroupService:
    return GroupService(repo=group_repo)


# ── Resources ─────────────────────────────────────────────────────────────────

@router.get("/resources", status_code=status.HTTP_200_OK)
async def get_resources(
    account_id:         str,
    owned_page:       int        = Query(1,  ge=1, description="Page for owned resources"),
    owned_page_size:  int        = Query(10, ge=1, description="Page size for owned resources"),
    shared_page:      int        = Query(1,  ge=1, description="Page for shared resources"),
    shared_page_size: int        = Query(10, ge=1, description="Page size for shared resources"),
    _:                object     = Depends(require_api_key("acl")),
    me:               DTO.UserDTO = Depends(MX.get_current_user),
    service:          ACLService  = Depends(get_acl_service),
):
    t1     = T.time()
    result = await service.get_user_resources(
        account_id       = account_id,
        user_id          = me.key,
        owned_page       = owned_page,
        owned_page_size  = owned_page_size,
        shared_page      = shared_page,
        shared_page_size = shared_page_size,
    )
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("acl.get_resources.error", started_at=t1, error=err, actor_user_id=me.key))
        raise err.to_http_exception()
    log.info(build_log_payload("acl.get_resources", started_at=t1, actor_user_id=me.key))
    return result.unwrap()


@router.post("/claim", status_code=status.HTTP_204_NO_CONTENT)
async def claim_resource(
    account_id: str,
    dto:     ClaimResourceDTO,
    _:       object      = Depends(require_api_key("acl")),
    me:      DTO.UserDTO  = Depends(MX.get_current_user),
    service: ACLService   = Depends(get_acl_service),
):
    t1     = T.time()
    result = await service.claim_resource(account_id=account_id, user_id=me.key, resource_id=dto.resource_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("acl.claim.error", started_at=t1, error=err, actor_user_id=me.key, resource_id=dto.resource_id))
        raise err.to_http_exception()
    log.info(build_log_payload("acl.claim", started_at=t1, actor_user_id=me.key, resource_id=dto.resource_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/grant", status_code=status.HTTP_204_NO_CONTENT)
async def grant_permission(
    account_id: str,
    dto:     GrantOrRevokeDTO,
    _:       object      = Depends(require_api_key("acl")),
    me:      DTO.UserDTO  = Depends(MX.get_current_user),
    service: ACLService   = Depends(get_acl_service),
):
    t1             = T.time()
    principal_type = PrincipalType((dto.principal_type or "USER").upper().strip())
    result         = await service.grant(
        account_id     = account_id,
        caller_id      = me.key,
        resource_id    = dto.resource_id,
        principal_id   = dto.principal_id,
        principal_type = principal_type,
        permissions    = dto.permissions,
    )
    if result.is_err:
        err = result.unwrap_err()
        log.error(
            build_log_payload(
                "acl.grant.error",
                started_at=t1,
                error=err,
                actor_user_id=me.key,
                resource_id=dto.resource_id,
                principal_id=dto.principal_id,
                principal_type=principal_type.value,
                permissions=dto.permissions,
            )
        )
        raise err.to_http_exception()
    log.info(
        build_log_payload(
            "acl.grant",
            started_at=t1,
            actor_user_id=me.key,
            resource_id=dto.resource_id,
            principal_id=dto.principal_id,
            principal_type=principal_type.value,
            permissions=dto.permissions,
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_permission(
    account_id: str,
    dto:     GrantOrRevokeDTO,
    _:       object      = Depends(require_api_key("acl")),
    me:      DTO.UserDTO  = Depends(MX.get_current_user),
    service: ACLService   = Depends(get_acl_service),
):
    t1     = T.time()
    result = await service.revoke(
        account_id   = account_id,
        caller_id    = me.key,
        resource_id  = dto.resource_id,
        principal_id = dto.principal_id,
        permissions  = dto.permissions,
    )
    if result.is_err:
        err = result.unwrap_err()
        log.error(
            build_log_payload(
                "acl.revoke.error",
                started_at=t1,
                error=err,
                actor_user_id=me.key,
                resource_id=dto.resource_id,
                principal_id=dto.principal_id,
                permissions=dto.permissions,
            )
        )
        raise err.to_http_exception()
    log.info(
        build_log_payload(
            "acl.revoke",
            started_at=t1,
            actor_user_id=me.key,
            resource_id=dto.resource_id,
            principal_id=dto.principal_id,
            permissions=dto.permissions,
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/check", status_code=status.HTTP_200_OK)
async def check_permission(
    account_id: str,
    dto:     CheckDTO,
    _:       object      = Depends(require_api_key("acl")),
    me:      DTO.UserDTO  = Depends(MX.get_current_user),
    service: ACLService   = Depends(get_acl_service),
):
    t1     = T.time()
    result = await service.check(
        account_id  = account_id,
        user_id     = me.key,
        resource_id = dto.resource_id,
        permissions = dto.permissions,
    )
    if result.is_err:
        err = result.unwrap_err()
        log.error(
            build_log_payload(
                "acl.check.error",
                started_at=t1,
                error=err,
                actor_user_id=me.key,
                resource_id=dto.resource_id,
                permissions=dto.permissions,
            )
        )
        raise err.to_http_exception()
    has_permission = result.unwrap()
    log.info(
        build_log_payload(
            "acl.check",
            started_at=t1,
            actor_user_id=me.key,
            resource_id=dto.resource_id,
            permissions=dto.permissions,
            has_permission=has_permission,
        )
    )
    return {"has_permission": has_permission}


# ── Groups ────────────────────────────────────────────────────────────────────

@router.post("/groups", status_code=status.HTTP_201_CREATED)
async def create_group(
    account_id: str,
    dto:     DTO.CreateGroupDTO,
    _:       object       = Depends(require_api_key("acl")),
    me:      DTO.UserDTO   = Depends(MX.get_current_user),
    service: GroupService  = Depends(get_group_service),
):
    t1     = T.time()
    result = await service.create_group(account_id=account_id, owner_id=me.key, name=dto.name, description=dto.description or "")
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("acl.create_group.error", started_at=t1, error=err, actor_user_id=me.key, group_name=dto.name))
        raise err.to_http_exception()
    group_id = result.unwrap()
    log.info(build_log_payload("acl.create_group", started_at=t1, actor_user_id=me.key, group_id=group_id, group_name=dto.name))
    return {"group_id": group_id}


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    account_id: str,
    group_id: str,
    _:        object       = Depends(require_api_key("acl")),
    me:       DTO.UserDTO   = Depends(MX.get_current_user),
    service:  GroupService  = Depends(get_group_service),
):
    t1     = T.time()
    result = await service.delete_group(account_id=account_id, caller_id=me.key, group_id=group_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("acl.delete_group.error", started_at=t1, error=err, actor_user_id=me.key, group_id=group_id))
        raise err.to_http_exception()
    log.info(build_log_payload("acl.delete_group", started_at=t1, actor_user_id=me.key, group_id=group_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/groups/{group_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def add_members(
    account_id: str,
    group_id: str,
    dto:      MembersDTO,
    _:        object       = Depends(require_api_key("acl")),
    me:       DTO.UserDTO   = Depends(MX.get_current_user),
    service:  GroupService  = Depends(get_group_service),
):
    t1     = T.time()
    result = await service.add_members(account_id=account_id, caller_id=me.key, group_id=group_id, user_ids=dto.members)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("acl.add_members.error", started_at=t1, error=err, actor_user_id=me.key, group_id=group_id, members=dto.members))
        raise err.to_http_exception()
    log.info(build_log_payload("acl.add_members", started_at=t1, actor_user_id=me.key, group_id=group_id, member_count=len(dto.members), members=dto.members))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/groups/{group_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def remove_members(
    account_id: str,
    group_id: str,
    dto:      MembersDTO,
    _:        object       = Depends(require_api_key("acl")),
    me:       DTO.UserDTO   = Depends(MX.get_current_user),
    service:  GroupService  = Depends(get_group_service),
):
    t1     = T.time()
    result = await service.remove_members(account_id=account_id, caller_id=me.key, group_id=group_id, user_ids=dto.members)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("acl.remove_members.error", started_at=t1, error=err, actor_user_id=me.key, group_id=group_id, members=dto.members))
        raise err.to_http_exception()
    log.info(build_log_payload("acl.remove_members", started_at=t1, actor_user_id=me.key, group_id=group_id, member_count=len(dto.members), members=dto.members))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Data Discovery Endpoints ──────────────────────────────────────────────────

@router.get("/groups/list", status_code=status.HTTP_200_OK)
async def list_groups_discovery(
    account_id: str,
    _:       object       = Depends(require_api_key("acl")),
    service: GroupService  = Depends(get_group_service),
):
    t1     = T.time()
    result = await service.list_groups(account_id=account_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("acl.list_groups_discovery.error", started_at=t1, error=err))
        raise err.to_http_exception()
    groups = result.unwrap()
    log.info(build_log_payload("acl.list_groups_discovery", started_at=t1, group_count=len(groups)))
    return [{"id": g.group_id, "name": g.name} for g in groups]


@router.get("/principals/list", status_code=status.HTTP_200_OK)
async def list_principals_discovery(
    account_id: str,
    _:       object       = Depends(require_api_key("acl")),
    service: GroupService  = Depends(get_group_service),
):
    t1     = T.time()
    result = await service.list_principals(account_id=account_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("acl.list_principals_discovery.error", started_at=t1, error=err))
        raise err.to_http_exception()
    principals = result.unwrap()
    log.info(build_log_payload("acl.list_principals_discovery", started_at=t1, principal_count=len(principals)))
    return principals


@router.get("/resources/list", status_code=status.HTTP_200_OK)
async def list_resources_discovery(
    account_id: str,
    _:       object       = Depends(require_api_key("acl")),
    service: ACLService    = Depends(get_acl_service),
):
    t1     = T.time()
    result = await service.list_resources(account_id=account_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("acl.list_resources_discovery.error", started_at=t1, error=err))
        raise err.to_http_exception()
    resources = result.unwrap()
    log.info(build_log_payload("acl.list_resources_discovery", started_at=t1, resource_count=len(resources)))
    return resources
