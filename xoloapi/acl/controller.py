import time as T
from fastapi import APIRouter, Depends, Query, Response, status
from xoloapi.log import Log

import xoloapi.config as Cfg
import xoloapi.db as DbX
import xoloapi.middleware as MX
import commonx.dto.xolo as DTO

from xoloapi.accounts.dependencies import require_existing_account
from xoloapi.acl.application.acl_service import ACLService
from xoloapi.groups.application.group_service import GroupService
from xoloapi.acl.domain.value_objects import Permission, PrincipalType
from xoloapi.acl.dto import (
    CheckDTO, ClaimResourceDTO, GrantOrRevokeDTO, GroupDetailDTO,
    GroupMembershipDTO, MembersDTO, PaginatedDTO, ResourceDetailDTO, UserResourcesDTO,
    EffectiveAccessDTO, ResourceGrantDTO, ResourceGrantsDTO,
    ServiceClaimResourceDTO, ServiceCreateGroupDTO, ServiceResourceDetailDTO,
    ServiceUserResourcesDTO, TransferGroupOwnerDTO, TransferResourceOwnerDTO,
)
from xoloapi.acl.infrastructure.mongo_resource_policy_repository import MongoResourcePolicyRepository
from xoloapi.groups.infrastructure.mongo_security_group_repository import MongoSecurityGroupRepository
from xoloapi.users.infrastructure.mongo_repository import MongoUsersRepository
from xoloapi.db.constants import CollectionNames
from xoloapi.log.format import build_log_payload
from xoloapi.middleware.apikey import require_api_key, require_admin_or_api_key, require_service_api_key
from xoloapi.apikeys.domain.aggregates import APIKey

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

def _users_repo() -> MongoUsersRepository:
    return MongoUsersRepository(
        collection=DbX.get_database()[CollectionNames.USERS_COLLECTION_NAME],
    )

def get_acl_service(
    policy_repo: MongoResourcePolicyRepository = Depends(_policy_repo),
    group_repo:  MongoSecurityGroupRepository  = Depends(_group_repo),
    users_repo:  MongoUsersRepository          = Depends(_users_repo),
) -> ACLService:
    return ACLService(policy_repo=policy_repo, group_repo=group_repo, users_repo=users_repo)

def get_group_service(
    group_repo: MongoSecurityGroupRepository = Depends(_group_repo),
    users_repo: MongoUsersRepository         = Depends(_users_repo),
) -> GroupService:
    return GroupService(repo=group_repo, users_repo=users_repo)


def _principal_type(value: str | PrincipalType) -> PrincipalType:
    return value if isinstance(value, PrincipalType) else PrincipalType(value.upper().strip())


async def _resource_grants_dto(account_id: str, policy, service: ACLService) -> ResourceGrantsDTO:
    grants: list[ResourceGrantDTO] = []
    for grant in policy.grants:
        grants.append(ResourceGrantDTO(
            grant_id=grant.grant_id,
            principal_id=grant.principal.id,
            principal_type=grant.principal.type.value,
            principal_name=await service.principal_name(account_id, grant.principal),
            permissions={p.value for p in (set(Permission) if grant.is_owner else grant.permissions)},
            is_owner=grant.is_owner,
        ))
    return ResourceGrantsDTO(resource_id=policy.resource_id, grants=grants)


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
    t1 = T.time()

    groups_result = await service.get_user_groups(account_id, me.key)
    if groups_result.is_err:
        err = groups_result.unwrap_err()
        log.error(build_log_payload("acl.get_resources.error", started_at=t1, error=err, actor_user_id=me.key))
        raise err.to_http_exception()
    groups    = groups_result.unwrap()
    group_map = {g.group_id: g.name for g in groups}

    owned_result = await service.get_owned_resources_page(account_id, me.key, owned_page, owned_page_size)
    if owned_result.is_err:
        err = owned_result.unwrap_err()
        log.error(build_log_payload("acl.get_resources.error", started_at=t1, error=err, actor_user_id=me.key))
        raise err.to_http_exception()
    owned = owned_result.unwrap()

    all_pids       = [me.key] + list(group_map.keys())
    exclude_ids    = [p.resource_id for p in owned.items]
    shared_result  = await service.get_shared_resources_page(account_id, all_pids, exclude_ids, shared_page, shared_page_size)
    if shared_result.is_err:
        err = shared_result.unwrap_err()
        log.error(build_log_payload("acl.get_resources.error", started_at=t1, error=err, actor_user_id=me.key))
        raise err.to_http_exception()
    shared = shared_result.unwrap()

    shared_items: list[ResourceDetailDTO] = []
    for p in shared.items:
        source = "Direct"
        for grant in p.grants:
            if grant.principal.id in group_map:
                source = f"Group: {group_map[grant.principal.id]}"
                break
        shared_items.append(ResourceDetailDTO(
            resource_id   = p.resource_id,
            permissions   = {perm.value for perm in p.effective_permissions(all_pids)},
            access_source = source,
        ))

    log.info(build_log_payload("acl.get_resources", started_at=t1, actor_user_id=me.key))
    return UserResourcesDTO(
        user_id         = me.key,
        groups          = [GroupDetailDTO(id=g.group_id, name=g.name, my_role="owner" if g.is_owned_by(me.key) else "member") for g in groups],
        owned_resources = PaginatedDTO[ResourceDetailDTO](
            items       = [ResourceDetailDTO(resource_id=p.resource_id, permissions={perm.value for perm in p.effective_permissions([me.key])}, access_source="Owner") for p in owned.items],
            total_count = owned.total,
            page        = owned.page,
            page_size   = owned.size,
            total_pages = owned.total_pages,
        ),
        shared_resources = PaginatedDTO[ResourceDetailDTO](
            items       = shared_items,
            total_count = shared.total,
            page        = shared.page,
            page_size   = shared.size,
            total_pages = shared.total_pages,
        ),
    )


@router.get("/resources/{resource_id}/grants", response_model=ResourceGrantsDTO)
async def list_resource_grants(
    account_id: str,
    resource_id: str,
    _:       object       = Depends(require_api_key("acl")),
    me:      DTO.UserDTO  = Depends(MX.get_current_user),
    service: ACLService   = Depends(get_acl_service),
):
    result = await service.get_policy_for_caller(
        account_id,
        resource_id,
        caller_id=me.key,
        is_admin=Cfg.is_superadmin(me),
    )
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    return await _resource_grants_dto(account_id, result.unwrap(), service)


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
        principal_username = dto.principal_username,
        is_admin       = Cfg.is_superadmin(me),
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
        principal_type = _principal_type(dto.principal_type or "USER"),
        principal_username = dto.principal_username,
        is_admin     = Cfg.is_superadmin(me),
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
    t1      = T.time()
    subject = me.key
    subject_type = PrincipalType.USER
    if dto.principal_username or dto.principal_id:
        subject_type = _principal_type(dto.principal_type or "USER")
        principal = await service.resolve_principal(
            account_id,
            subject_type,
            principal_id=dto.principal_id,
            principal_username=dto.principal_username,
        )
        if principal.is_err:
            raise principal.unwrap_err().to_http_exception()
        subject = principal.unwrap().id
    result  = await service.check(
        account_id  = account_id,
        user_id     = subject,
        resource_id = dto.resource_id,
        permissions = dto.permissions,
        principal_type = subject_type,
    )
    if result.is_err:
        err = result.unwrap_err()
        log.error(
            build_log_payload(
                "acl.check.error",
                started_at=t1,
                error=err,
                actor_user_id=me.key,
                principal_id=subject,
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
            principal_id=subject,
            resource_id=dto.resource_id,
            permissions=dto.permissions,
            has_permission=has_permission,
        )
    )
    return {"has_permission": has_permission}


# ── Trusted service operations ───────────────────────────────────────────────

@router.post("/service/claim", status_code=status.HTTP_204_NO_CONTENT)
async def service_claim_resource(
    account_id: str,
    dto: ServiceClaimResourceDTO,
    api_key: APIKey = Depends(require_service_api_key("acl")),
    service: ACLService = Depends(get_acl_service),
):
    t1 = T.time()
    result = await service.claim_resource_for_principal(
        account_id=account_id,
        principal_id=dto.owner_id,
        principal_type=_principal_type(dto.owner_type),
        resource_id=dto.resource_id,
    )
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("acl.service.claim.error", started_at=t1, error=err, key_id=api_key.key_id, resource_id=dto.resource_id, principal_id=dto.owner_id))
        raise err.to_http_exception()
    log.info(build_log_payload("acl.service.claim", started_at=t1, key_id=api_key.key_id, resource_id=dto.resource_id, principal_id=dto.owner_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/service/grant", status_code=status.HTTP_204_NO_CONTENT)
async def service_grant_permission(
    account_id: str,
    dto: GrantOrRevokeDTO,
    api_key: APIKey = Depends(require_service_api_key("acl")),
    service: ACLService = Depends(get_acl_service),
):
    t1 = T.time()
    result = await service.grant(
        account_id=account_id,
        caller_id=f"service:{api_key.key_id}",
        resource_id=dto.resource_id,
        principal_id=dto.principal_id,
        principal_type=_principal_type(dto.principal_type or "USER"),
        permissions=dto.permissions,
        is_admin=True,
    )
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("acl.service.grant.error", started_at=t1, error=err, key_id=api_key.key_id, resource_id=dto.resource_id, principal_id=dto.principal_id, permissions=dto.permissions))
        raise err.to_http_exception()
    log.info(build_log_payload("acl.service.grant", started_at=t1, key_id=api_key.key_id, resource_id=dto.resource_id, principal_id=dto.principal_id, permissions=dto.permissions))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/service/revoke", status_code=status.HTTP_204_NO_CONTENT)
async def service_revoke_permission(
    account_id: str,
    dto: GrantOrRevokeDTO,
    api_key: APIKey = Depends(require_service_api_key("acl")),
    service: ACLService = Depends(get_acl_service),
):
    t1 = T.time()
    result = await service.revoke(
        account_id=account_id,
        caller_id=f"service:{api_key.key_id}",
        resource_id=dto.resource_id,
        principal_id=dto.principal_id,
        permissions=dto.permissions,
        is_admin=True,
    )
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("acl.service.revoke.error", started_at=t1, error=err, key_id=api_key.key_id, resource_id=dto.resource_id, principal_id=dto.principal_id, permissions=dto.permissions))
        raise err.to_http_exception()
    log.info(build_log_payload("acl.service.revoke", started_at=t1, key_id=api_key.key_id, resource_id=dto.resource_id, principal_id=dto.principal_id, permissions=dto.permissions))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/service/resources/{resource_id}/users/{user_id}/access", response_model=EffectiveAccessDTO)
async def service_effective_access(
    account_id: str,
    resource_id: str,
    user_id: str,
    api_key: APIKey = Depends(require_service_api_key("acl")),
    service: ACLService = Depends(get_acl_service),
):
    t1 = T.time()
    result = await service.effective_access(account_id, user_id, resource_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("acl.service.effective_access.error", started_at=t1, error=err, key_id=api_key.key_id, resource_id=resource_id, principal_id=user_id))
        raise err.to_http_exception()
    permissions, is_owner, group_ids = result.unwrap()
    log.info(build_log_payload("acl.service.effective_access", started_at=t1, key_id=api_key.key_id, resource_id=resource_id, principal_id=user_id, is_owner=is_owner))
    return EffectiveAccessDTO(
        user_id=user_id,
        resource_id=resource_id,
        is_owner=is_owner,
        permissions={p.value for p in permissions},
        group_ids=group_ids,
    )


@router.get("/service/resources/{resource_id}/grants", response_model=ResourceGrantsDTO)
async def service_list_resource_grants(
    account_id: str,
    resource_id: str,
    api_key: APIKey = Depends(require_service_api_key("acl")),
    service: ACLService = Depends(get_acl_service),
):
    result = await service.get_policy(account_id, resource_id)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    policy = result.unwrap()
    log.info(build_log_payload("acl.service.grants.list", key_id=api_key.key_id, resource_id=resource_id, grant_count=len(policy.grants)))
    return await _resource_grants_dto(account_id, policy, service)


@router.get("/service/users/{user_id}/resources", response_model=ServiceUserResourcesDTO)
async def service_get_user_resources(
    account_id: str,
    user_id: str,
    owned_page: int = Query(1, ge=1),
    owned_page_size: int = Query(10, ge=1),
    shared_page: int = Query(1, ge=1),
    shared_page_size: int = Query(10, ge=1),
    api_key: APIKey = Depends(require_service_api_key("acl")),
    service: ACLService = Depends(get_acl_service),
):
    groups_result = await service.get_user_groups(account_id, user_id)
    if groups_result.is_err:
        raise groups_result.unwrap_err().to_http_exception()
    groups = groups_result.unwrap()
    group_ids = [g.group_id for g in groups]
    principal_ids = [user_id] + group_ids

    owned_result = await service.get_owned_resources_page(account_id, user_id, owned_page, owned_page_size)
    if owned_result.is_err:
        raise owned_result.unwrap_err().to_http_exception()
    owned = owned_result.unwrap()
    exclude_ids = [p.resource_id for p in owned.items]
    shared_result = await service.get_shared_resources_page(account_id, principal_ids, exclude_ids, shared_page, shared_page_size)
    if shared_result.is_err:
        raise shared_result.unwrap_err().to_http_exception()
    shared = shared_result.unwrap()

    def detail(policy):
        access_groups = [g.group_id for g in groups if any(grant.principal.id == g.group_id for grant in policy.grants)]
        return ServiceResourceDetailDTO(
            resource_id=policy.resource_id,
            permissions={p.value for p in policy.effective_permissions(principal_ids)},
            is_owner=policy.is_owned_by_any(principal_ids),
            access_group_ids=access_groups,
        )

    log.info(build_log_payload("acl.service.user_resources", key_id=api_key.key_id, principal_id=user_id))
    return ServiceUserResourcesDTO(
        user_id=user_id,
        groups=[GroupDetailDTO(id=g.group_id, name=g.name, my_role="owner" if g.is_owned_by(user_id) else "member") for g in groups],
        owned_resources=PaginatedDTO[ServiceResourceDetailDTO](
            items=[detail(p) for p in owned.items], total_count=owned.total,
            page=owned.page, page_size=owned.size, total_pages=owned.total_pages,
        ),
        shared_resources=PaginatedDTO[ServiceResourceDetailDTO](
            items=[detail(p) for p in shared.items], total_count=shared.total,
            page=shared.page, page_size=shared.size, total_pages=shared.total_pages,
        ),
    )


@router.post("/service/resources/{resource_id}/owner", status_code=status.HTTP_204_NO_CONTENT)
async def service_transfer_resource_owner(
    account_id: str,
    resource_id: str,
    dto: TransferResourceOwnerDTO,
    api_key: APIKey = Depends(require_service_api_key("acl")),
    service: ACLService = Depends(get_acl_service),
):
    result = await service.transfer_owner(
        account_id=account_id,
        resource_id=resource_id,
        principal_id=dto.principal_id,
        principal_type=_principal_type(dto.principal_type),
        keep_previous_permissions=dto.keep_previous_permissions,
    )
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    log.info(build_log_payload("acl.service.owner.transfer", key_id=api_key.key_id, resource_id=resource_id, principal_id=dto.principal_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/service/resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def service_delete_resource_policy(
    account_id: str,
    resource_id: str,
    api_key: APIKey = Depends(require_service_api_key("acl")),
    service: ACLService = Depends(get_acl_service),
):
    result = await service.delete_resource(account_id, resource_id, is_admin=True)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    log.info(build_log_payload("acl.service.resource.delete", key_id=api_key.key_id, resource_id=resource_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/service/groups", status_code=status.HTTP_201_CREATED)
async def service_create_group(
    account_id: str,
    dto: ServiceCreateGroupDTO,
    api_key: APIKey = Depends(require_service_api_key("acl")),
    service: GroupService = Depends(get_group_service),
):
    result = await service.create_group(account_id, dto.owner_id, dto.name, dto.description or "")
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    group_id = result.unwrap()
    log.info(build_log_payload("acl.service.group.create", key_id=api_key.key_id, group_id=group_id, principal_id=dto.owner_id))
    return {"group_id": group_id}


@router.post("/service/groups/{group_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def service_add_group_members(
    account_id: str,
    group_id: str,
    dto: MembersDTO,
    api_key: APIKey = Depends(require_service_api_key("acl")),
    service: GroupService = Depends(get_group_service),
):
    result = await service.add_members_admin(account_id, group_id, dto.members)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    log.info(build_log_payload("acl.service.group.members.add", key_id=api_key.key_id, group_id=group_id, members=dto.members))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/service/groups/{group_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def service_remove_group_members(
    account_id: str,
    group_id: str,
    dto: MembersDTO,
    api_key: APIKey = Depends(require_service_api_key("acl")),
    service: GroupService = Depends(get_group_service),
):
    result = await service.remove_members_admin(account_id, group_id, dto.members)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    log.info(build_log_payload("acl.service.group.members.remove", key_id=api_key.key_id, group_id=group_id, members=dto.members))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/service/groups/{group_id}/members")
async def service_list_group_members(
    account_id: str,
    group_id: str,
    api_key: APIKey = Depends(require_service_api_key("acl")),
    service: GroupService = Depends(get_group_service),
):
    result = await service.list_members(account_id, group_id)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    members = result.unwrap()
    log.info(build_log_payload("acl.service.group.members.list", key_id=api_key.key_id, group_id=group_id, member_count=len(members)))
    return [{"user_id": m.user_id, "joined_at": m.joined_at} for m in members]


@router.post("/service/groups/{group_id}/owner", status_code=status.HTTP_204_NO_CONTENT)
async def service_transfer_group_owner(
    account_id: str,
    group_id: str,
    dto: TransferGroupOwnerDTO,
    api_key: APIKey = Depends(require_service_api_key("acl")),
    service: GroupService = Depends(get_group_service),
):
    result = await service.transfer_owner_admin(account_id, group_id, dto.user_id, dto.keep_previous_as_member)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    log.info(build_log_payload("acl.service.group.owner.transfer", key_id=api_key.key_id, group_id=group_id, principal_id=dto.user_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/service/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def service_delete_group(
    account_id: str,
    group_id: str,
    api_key: APIKey = Depends(require_service_api_key("acl")),
    service: GroupService = Depends(get_group_service),
):
    result = await service.delete_group_admin(account_id, group_id)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    log.info(build_log_payload("acl.service.group.delete", key_id=api_key.key_id, group_id=group_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    result = (
        await service.delete_group_admin(account_id=account_id, group_id=group_id)
        if Cfg.is_superadmin(me)
        else await service.delete_group(account_id=account_id, caller_id=me.key, group_id=group_id)
    )
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
    resolved = await service.resolve_usernames(account_id, dto.usernames)
    if resolved.is_err:
        raise resolved.unwrap_err().to_http_exception()
    user_ids = list(dict.fromkeys(dto.members + resolved.unwrap()))
    if Cfg.is_superadmin(me):
        validated = await service.validate_user_ids(account_id, user_ids)
        if validated.is_err:
            raise validated.unwrap_err().to_http_exception()
        result = await service.add_members_admin(account_id, group_id, validated.unwrap())
    else:
        result = await service.add_members(
            account_id=account_id,
            caller_id=me.key,
            group_id=group_id,
            user_ids=user_ids,
        )
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
    resolved = await service.resolve_usernames(account_id, dto.usernames)
    if resolved.is_err:
        raise resolved.unwrap_err().to_http_exception()
    user_ids = list(dict.fromkeys(dto.members + resolved.unwrap()))
    if Cfg.is_superadmin(me):
        validated = await service.validate_user_ids(account_id, user_ids)
        if validated.is_err:
            raise validated.unwrap_err().to_http_exception()
        result = await service.remove_members_admin(account_id, group_id, validated.unwrap())
    else:
        result = await service.remove_members(
            account_id=account_id,
            caller_id=me.key,
            group_id=group_id,
            user_ids=user_ids,
        )
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("acl.remove_members.error", started_at=t1, error=err, actor_user_id=me.key, group_id=group_id, members=dto.members))
        raise err.to_http_exception()
    log.info(build_log_payload("acl.remove_members", started_at=t1, actor_user_id=me.key, group_id=group_id, member_count=len(dto.members), members=dto.members))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/groups/{group_id}/members", status_code=status.HTTP_200_OK)
async def list_group_members(
    account_id: str,
    group_id: str,
    _:       object       = Depends(require_api_key("acl")),
    me:      DTO.UserDTO  = Depends(MX.get_current_user),
    service: GroupService = Depends(get_group_service),
):
    result = await service.list_members_authorized(
        account_id,
        group_id,
        caller_id=me.key,
        is_admin=Cfg.is_superadmin(me),
    )
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    details = []
    for member in result.unwrap():
        username = member.user_id
        if service.users_repo is not None:
            maybe_user = await service.users_repo.find_by_id(member.user_id, account_id=account_id)
            if maybe_user.is_some:
                username = maybe_user.unwrap().username
        details.append({"user_id": member.user_id, "username": username, "joined_at": member.joined_at})
    return details


@router.get("/groups/{group_id}/members/{user_id}", status_code=status.HTTP_200_OK, response_model=GroupMembershipDTO)
async def check_group_membership(
    account_id: str,
    group_id:   str,
    user_id:    str,
    _:          object       = Depends(require_api_key("acl")),
    me:         DTO.UserDTO   = Depends(MX.get_current_user),
    service:    GroupService  = Depends(get_group_service),
):
    t1     = T.time()
    result = await service.is_member(account_id=account_id, user_id=user_id, group_id=group_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("acl.check_membership.error", started_at=t1, error=err, actor_user_id=me.key, group_id=group_id, user_id=user_id))
        raise err.to_http_exception()
    is_member = result.unwrap()
    log.info(build_log_payload("acl.check_membership", started_at=t1, actor_user_id=me.key, group_id=group_id, user_id=user_id, is_member=is_member))
    return GroupMembershipDTO(user_id=user_id, group_id=group_id, is_member=is_member)


# ── Data Discovery Endpoints ──────────────────────────────────────────────────

@router.get("/groups/list", status_code=status.HTTP_200_OK)
async def list_groups_discovery(
    account_id: str,
    _:       object       = Depends(require_admin_or_api_key("acl")),
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
    return [{
        "id": g.group_id,
        "name": g.name,
        "description": g.description,
        "owner_id": g.owner_id,
    } for g in groups]


@router.get("/principals/list", status_code=status.HTTP_200_OK)
async def list_principals_discovery(
    account_id: str,
    _:       object       = Depends(require_admin_or_api_key("acl")),
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
    _:       object       = Depends(require_admin_or_api_key("acl")),
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
