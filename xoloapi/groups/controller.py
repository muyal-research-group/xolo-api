from __future__ import annotations

import math
from fastapi import APIRouter, Depends, Query, Response, status

import commonx.dto.xolo as DTO
import xoloapi.config as Cfg
import xoloapi.db as DbX
import xoloapi.middleware as MX
from xoloapi.accounts.dependencies import require_existing_account
from xoloapi.db.constants import CollectionNames
from xoloapi.groups.application.group_service import GroupService
from xoloapi.groups.dto import (
    CreateGroupDTO, GroupDTO, GroupMemberDTO, GroupMemberPageDTO, GroupMembersDTO,
    GroupPageDTO, GroupReferenceDTO, GroupStatusDTO, GroupUsageDTO,
    TransferOwnerDTO, UpdateGroupDTO,
)
from xoloapi.groups.infrastructure.mongo_security_group_repository import MongoSecurityGroupRepository
from xoloapi.middleware.apikey import require_api_key, require_any_api_key
from xoloapi.users.infrastructure.mongo_repository import MongoUsersRepository


router = APIRouter(
    prefix="/accounts/{account_id}/groups",
    tags=["groups"],
    dependencies=[Depends(require_existing_account)],
)


def _group_repo() -> MongoSecurityGroupRepository:
    return MongoSecurityGroupRepository(
        DbX.get_database(),
        CollectionNames.SECURITY_GROUPS_COLLECTION_NAME,
        CollectionNames.GROUP_MEMBERS_COLLECTION_NAME,
    )


def _users_repo() -> MongoUsersRepository:
    return MongoUsersRepository(DbX.get_database()[CollectionNames.USERS_COLLECTION_NAME])


async def _usage(account_id: str, group_id: str) -> dict:
    db = DbX.get_database()
    acl: list[dict] = []
    async for doc in db[CollectionNames.ACL_RESOURCE_POLICIES_COLLECTION_NAME].find(
        {"account_id": account_id, "grants.principal_id": group_id},
        {"_id": 0, "resource_id": 1, "grants": 1},
    ):
        for grant in doc.get("grants", []):
            if grant.get("principal_id") == group_id:
                acl.append({
                    "resource_id": doc["resource_id"],
                    "grant_id": grant.get("grant_id"),
                    "permissions": grant.get("permissions", []),
                    "is_owner": grant.get("is_owner", False),
                })
    rbac: list[dict] = []
    async for doc in db[CollectionNames.RBAC_ASSIGNMENTS_COLLECTION_NAME].find(
        {"account_id": account_id, "subject_id": group_id, "subject_type": "GROUP"},
        {"_id": 1, "role_id": 1},
    ):
        rbac.append({"assignment_id": str(doc["_id"]), "role_id": doc["role_id"]})
    return {"acl_grants": acl, "rbac_assignments": rbac}


def get_group_service(
    repo: MongoSecurityGroupRepository = Depends(_group_repo),
    users: MongoUsersRepository = Depends(_users_repo),
) -> GroupService:
    return GroupService(repo, users, _usage)


async def _owner_username(service: GroupService, account_id: str, owner_id: str) -> str | None:
    if service.users_repo is None:
        return None
    user = await service.users_repo.find_by_id(owner_id, account_id=account_id)
    return user.unwrap().username if user.is_some else None


async def _to_group(service: GroupService, group) -> GroupDTO:
    members = await service.repo.list_members(group.account_id, group.group_id)
    usage = await service.usage(group.account_id, group.group_id)
    member_count = len(members.unwrap()) if members.is_ok else 0
    usage_value = usage.unwrap() if usage.is_ok else {"acl_grants": [], "rbac_assignments": []}
    return GroupDTO(
        **group.model_dump(),
        owner_username=await _owner_username(service, group.account_id, group.owner_id),
        member_count=member_count,
        acl_usage_count=len(usage_value["acl_grants"]),
        rbac_usage_count=len(usage_value["rbac_assignments"]),
    )


@router.get("/references", response_model=list[GroupReferenceDTO])
async def references(
    account_id: str,
    _: object = Depends(require_any_api_key("groups", "acl", "rbac")),
    service: GroupService = Depends(get_group_service),
):
    result = await service.list_groups(account_id)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    return [GroupReferenceDTO(group_id=g.group_id, name=g.name, is_active=g.is_active) for g in result.unwrap()]


@router.get("", response_model=GroupPageDTO)
async def list_groups(
    account_id: str,
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _: object = Depends(require_api_key("groups")),
    service: GroupService = Depends(get_group_service),
):
    result = await service.list_groups(account_id)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    needle = search.strip().casefold()
    groups = [g for g in result.unwrap() if not needle or needle in g.name.casefold()]
    total = len(groups)
    groups = groups[(page - 1) * page_size:page * page_size]
    return GroupPageDTO(
        items=[await _to_group(service, group) for group in groups],
        total_count=total, page=page, page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=GroupDTO)
async def create_group(
    account_id: str,
    dto: CreateGroupDTO,
    _: object = Depends(require_api_key("groups")),
    service: GroupService = Depends(get_group_service),
):
    result = await service.create_group_for_username(account_id, dto.owner_username, dto.name, dto.description or "")
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    found = await service.repo.find_by_id(account_id, result.unwrap())
    return await _to_group(service, found.unwrap().unwrap())


@router.get("/{group_id}", response_model=GroupDTO)
async def get_group(
    account_id: str,
    group_id: str,
    _: object = Depends(require_api_key("groups")),
    service: GroupService = Depends(get_group_service),
):
    result = await service.repo.find_by_id(account_id, group_id)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    if result.unwrap().is_none:
        from xoloapi.errors.base import NotFoundError
        raise NotFoundError("SecurityGroup", group_id).to_http_exception()
    return await _to_group(service, result.unwrap().unwrap())


@router.patch("/{group_id}", response_model=GroupDTO)
async def update_group(
    account_id: str,
    group_id: str,
    dto: UpdateGroupDTO,
    _: object = Depends(require_api_key("groups")),
    me: DTO.UserDTO = Depends(MX.get_current_user),
    service: GroupService = Depends(get_group_service),
):
    result = await service.update_group(
        account_id, group_id, me.key, name=dto.name, description=dto.description,
        is_admin=Cfg.is_superadmin(me),
    )
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    return await _to_group(service, result.unwrap())


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    account_id: str,
    group_id: str,
    _: object = Depends(require_api_key("groups")),
    me: DTO.UserDTO = Depends(MX.get_current_user),
    service: GroupService = Depends(get_group_service),
):
    result = await service.delete_group_admin(account_id, group_id) if Cfg.is_superadmin(me) else await service.delete_group(account_id, me.key, group_id)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{group_id}/owner", status_code=status.HTTP_204_NO_CONTENT)
async def transfer_owner(
    account_id: str,
    group_id: str,
    dto: TransferOwnerDTO,
    _: object = Depends(require_api_key("groups")),
    me: DTO.UserDTO = Depends(MX.get_current_user),
    service: GroupService = Depends(get_group_service),
):
    result = await service.transfer_owner(account_id, group_id, me.key, dto.owner_username, Cfg.is_superadmin(me))
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{group_id}/status", response_model=GroupDTO)
async def set_status(
    account_id: str,
    group_id: str,
    dto: GroupStatusDTO,
    _: object = Depends(require_api_key("groups")),
    service: GroupService = Depends(get_group_service),
):
    result = await service.set_status(account_id, group_id, dto.is_active)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    return await _to_group(service, result.unwrap())


@router.get("/{group_id}/members", response_model=GroupMemberPageDTO)
async def list_members(
    account_id: str,
    group_id: str,
    search: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _: object = Depends(require_api_key("groups")),
    me: DTO.UserDTO = Depends(MX.get_current_user),
    service: GroupService = Depends(get_group_service),
):
    result = await service.list_members_authorized(account_id, group_id, me.key, Cfg.is_superadmin(me))
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    rows = []
    for member in result.unwrap():
        user = await service.users_repo.find_by_id(member.user_id, account_id=account_id)
        if user.is_some:
            username = user.unwrap().username
            if not search or search.casefold() in username.casefold():
                rows.append(GroupMemberDTO(user_id=member.user_id, username=username, joined_at=member.joined_at))
    total = len(rows)
    return GroupMemberPageDTO(
        items=rows[(page - 1) * page_size:page * page_size], total_count=total,
        page=page, page_size=page_size, total_pages=math.ceil(total / page_size) if total else 0,
    )


async def _change_members(account_id, group_id, dto, me, service, add: bool):
    method = service.add_members_admin if add and Cfg.is_superadmin(me) else service.remove_members_admin if not add and Cfg.is_superadmin(me) else service.add_members if add else service.remove_members
    if Cfg.is_superadmin(me):
        resolved = await service.resolve_usernames(account_id, dto.usernames)
        if resolved.is_err:
            return resolved
        return await method(account_id, group_id, resolved.unwrap())
    return await method(account_id, me.key, group_id, [], dto.usernames)


@router.post("/{group_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def add_members(account_id: str, group_id: str, dto: GroupMembersDTO, _: object = Depends(require_api_key("groups")), me: DTO.UserDTO = Depends(MX.get_current_user), service: GroupService = Depends(get_group_service)):
    result = await _change_members(account_id, group_id, dto, me, service, True)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{group_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def remove_members(account_id: str, group_id: str, dto: GroupMembersDTO, _: object = Depends(require_api_key("groups")), me: DTO.UserDTO = Depends(MX.get_current_user), service: GroupService = Depends(get_group_service)):
    result = await _change_members(account_id, group_id, dto, me, service, False)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{group_id}/members/me", status_code=status.HTTP_204_NO_CONTENT)
async def leave_group(account_id: str, group_id: str, _: object = Depends(require_api_key("groups")), me: DTO.UserDTO = Depends(MX.get_current_user), service: GroupService = Depends(get_group_service)):
    result = await service.remove_members(account_id, me.key, group_id, [me.key])
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{group_id}/usage", response_model=GroupUsageDTO)
async def usage(account_id: str, group_id: str, _: object = Depends(require_api_key("groups")), service: GroupService = Depends(get_group_service)):
    result = await service.usage(account_id, group_id)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    return GroupUsageDTO(**result.unwrap())
