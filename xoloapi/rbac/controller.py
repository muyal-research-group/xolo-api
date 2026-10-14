import time as T
from fastapi import APIRouter, Depends, Query, Request, Response, status
from xoloapi.log import Log

import xoloapi.config as Cfg
import xoloapi.db as DbX
import xoloapi.middleware as MX
import commonx.dto.xolo as DTO

from xoloapi.accounts.dependencies import require_existing_account
from xoloapi.middleware.apikey import require_api_key, require_admin_or_api_key
from xoloapi.rbac.application.rbac_service import RBACService
from xoloapi.groups.infrastructure.mongo_security_group_repository import MongoSecurityGroupRepository
from xoloapi.rbac.dto import (
    AssignmentDTO,
    AssignRoleDTO,
    CheckPermissionDTO,
    CheckResultDTO,
    CreateRoleDTO,
    EffectivePermissionsDTO,
    HasRoleCheckDTO,
    HasRoleDTO,
    ParentRoleDTO,
    PermissionDTO,
    RoleDTO,
    UnassignRoleDTO,
    UpdateRoleDTO,
    UpdateAssignmentDTO,
)
from xoloapi.rbac.infrastructure.mongo_role_repository import MongoRoleRepository
from xoloapi.rbac.infrastructure.mongo_role_assignment_repository import MongoRoleAssignmentRepository
from xoloapi.rbac.infrastructure.mongo_permission_catalog_repository import MongoPermissionCatalogRepository
from xoloapi.users.infrastructure.mongo_repository import MongoUsersRepository
from xoloapi.db.constants import CollectionNames

log = Log(
    name                   = __name__,
    console_handler_filter = lambda x: True,
    interval               = Cfg.XOLO_LOG_INTERVAL,
    when                   = Cfg.XOLO_LOG_WHEN,
    path                   = Cfg.XOLO_LOG_PATH,
)

router = APIRouter(
    prefix="/accounts/{account_id}/rbac",
    tags=["rbac"],
    dependencies=[Depends(require_existing_account)],
)


# ── Dependency factories ──────────────────────────────────────────────────────

def _role_repo() -> MongoRoleRepository:
    return MongoRoleRepository(
        db              = DbX.get_database(),
        collection_name = CollectionNames.RBAC_ROLES_COLLECTION_NAME,
    )

def _assignment_repo() -> MongoRoleAssignmentRepository:
    return MongoRoleAssignmentRepository(
        db              = DbX.get_database(),
        collection_name = CollectionNames.RBAC_ASSIGNMENTS_COLLECTION_NAME,
    )

def _group_repo() -> MongoSecurityGroupRepository:
    return MongoSecurityGroupRepository(
        db          = DbX.get_database(),
        groups_col  = CollectionNames.SECURITY_GROUPS_COLLECTION_NAME,
        members_col = CollectionNames.GROUP_MEMBERS_COLLECTION_NAME,
    )

def _users_repo() -> MongoUsersRepository:
    return MongoUsersRepository(DbX.get_database()[CollectionNames.USERS_COLLECTION_NAME])

def _catalog_repo() -> MongoPermissionCatalogRepository:
    return MongoPermissionCatalogRepository(
        DbX.get_database(), CollectionNames.RBAC_PERMISSION_CATALOG_COLLECTION_NAME
    )

def get_rbac_service(
    role_repo:       MongoRoleRepository            = Depends(_role_repo),
    assignment_repo: MongoRoleAssignmentRepository  = Depends(_assignment_repo),
    group_repo:      MongoSecurityGroupRepository   = Depends(_group_repo),
    users_repo:      MongoUsersRepository           = Depends(_users_repo),
    catalog_repo:    MongoPermissionCatalogRepository = Depends(_catalog_repo),
) -> RBACService:
    return RBACService(
        role_repo=role_repo, assignment_repo=assignment_repo, group_repo=group_repo,
        users_repo=users_repo, catalog_repo=catalog_repo,
    )


# ── Role CRUD ─────────────────────────────────────────────────────────────────

@router.post("/roles", status_code=status.HTTP_201_CREATED, response_model=RoleDTO)
async def create_role(
    account_id: str,
    dto:     CreateRoleDTO,
    _:       object      = Depends(require_api_key("rbac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: RBACService = Depends(get_rbac_service),
):
    t1     = T.time()
    result = await service.create_role(account_id=account_id, name=dto.name, description=dto.description, permissions=dto.permissions)
    if result.is_err:
        err = result.unwrap_err()
        log.error({"action": "rbac.create_role.error", "name": dto.name, "error": str(err)})
        raise err.to_http_exception()
    role = result.unwrap()
    log.info({"action": "rbac.create_role", "role_id": role.role_id, "time": round(T.time() - t1, 4)})
    return RoleDTO(**role.model_dump())


@router.get("/roles", status_code=status.HTTP_200_OK)
async def list_roles(
    account_id: str,
    _:       object      = Depends(require_api_key("rbac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: RBACService = Depends(get_rbac_service),
):
    t1     = T.time()
    result = await service.list_roles(account_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error({"action": "rbac.list_roles.error", "error": str(err)})
        raise err.to_http_exception()
    roles = result.unwrap()
    log.info({"action": "rbac.list_roles", "count": len(roles), "time": round(T.time() - t1, 4)})
    return [RoleDTO(**r.model_dump()) for r in roles]


@router.get("/roles/{role_id}", status_code=status.HTTP_200_OK, response_model=RoleDTO)
async def get_role(
    account_id: str,
    role_id: str,
    _:       object      = Depends(require_api_key("rbac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: RBACService = Depends(get_rbac_service),
):
    t1     = T.time()
    result = await service.get_role(account_id, role_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error({"action": "rbac.get_role.error", "role_id": role_id, "error": str(err)})
        raise err.to_http_exception()
    role = result.unwrap()
    log.info({"action": "rbac.get_role", "role_id": role_id, "time": round(T.time() - t1, 4)})
    return RoleDTO(**role.model_dump())


@router.patch("/roles/{role_id}", status_code=status.HTTP_200_OK, response_model=RoleDTO)
async def update_role(
    account_id: str,
    role_id: str,
    dto:     UpdateRoleDTO,
    _:       object      = Depends(require_api_key("rbac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: RBACService = Depends(get_rbac_service),
):
    t1     = T.time()
    result = await service.update_role(
        account_id=account_id,
        role_id=role_id,
        name=dto.name,
        description=dto.description,
        description_set="description" in dto.model_fields_set,
    )
    if result.is_err:
        err = result.unwrap_err()
        log.error({"action": "rbac.update_role.error", "role_id": role_id, "error": str(err)})
        raise err.to_http_exception()
    role = result.unwrap()
    log.info({"action": "rbac.update_role", "role_id": role_id, "time": round(T.time() - t1, 4)})
    return RoleDTO(**role.model_dump())


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    account_id: str,
    role_id: str,
    _:       object      = Depends(require_api_key("rbac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: RBACService = Depends(get_rbac_service),
):
    t1     = T.time()
    result = await service.delete_role(account_id, role_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error({"action": "rbac.delete_role.error", "role_id": role_id, "error": str(err)})
        raise err.to_http_exception()
    log.info({"action": "rbac.delete_role", "role_id": role_id, "time": round(T.time() - t1, 4)})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Permissions ───────────────────────────────────────────────────────────────

@router.post("/roles/{role_id}/permissions", status_code=status.HTTP_200_OK, response_model=RoleDTO)
async def add_permission(
    account_id: str,
    role_id: str,
    dto:     PermissionDTO,
    _:       object      = Depends(require_api_key("rbac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: RBACService = Depends(get_rbac_service),
):
    t1     = T.time()
    result = await service.add_permission(account_id=account_id, role_id=role_id, permission=dto.permission)
    if result.is_err:
        err = result.unwrap_err()
        log.error({"action": "rbac.add_permission.error", "role_id": role_id, "error": str(err)})
        raise err.to_http_exception()
    role = result.unwrap()
    log.info({"action": "rbac.add_permission", "role_id": role_id, "permission": dto.permission, "time": round(T.time() - t1, 4)})
    return RoleDTO(**role.model_dump())


@router.delete("/roles/{role_id}/permissions", status_code=status.HTTP_200_OK, response_model=RoleDTO)
async def remove_permission(
    account_id: str,
    role_id: str,
    dto:     PermissionDTO,
    _:       object      = Depends(require_api_key("rbac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: RBACService = Depends(get_rbac_service),
):
    t1     = T.time()
    result = await service.remove_permission(account_id=account_id, role_id=role_id, permission=dto.permission)
    if result.is_err:
        err = result.unwrap_err()
        log.error({"action": "rbac.remove_permission.error", "role_id": role_id, "error": str(err)})
        raise err.to_http_exception()
    role = result.unwrap()
    log.info({"action": "rbac.remove_permission", "role_id": role_id, "permission": dto.permission, "time": round(T.time() - t1, 4)})
    return RoleDTO(**role.model_dump())


# ── Role hierarchy ────────────────────────────────────────────────────────────

@router.post("/roles/{role_id}/parents", status_code=status.HTTP_200_OK, response_model=RoleDTO)
async def add_parent(
    account_id: str,
    role_id: str,
    dto:     ParentRoleDTO,
    _:       object      = Depends(require_api_key("rbac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: RBACService = Depends(get_rbac_service),
):
    t1     = T.time()
    result = await service.add_parent(account_id=account_id, role_id=role_id, parent_role_id=dto.parent_role_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error({"action": "rbac.add_parent.error", "role_id": role_id, "error": str(err)})
        raise err.to_http_exception()
    role = result.unwrap()
    log.info({"action": "rbac.add_parent", "role_id": role_id, "parent": dto.parent_role_id, "time": round(T.time() - t1, 4)})
    return RoleDTO(**role.model_dump())


@router.delete("/roles/{role_id}/parents", status_code=status.HTTP_200_OK, response_model=RoleDTO)
async def remove_parent(
    account_id: str,
    role_id: str,
    dto:     ParentRoleDTO,
    _:       object      = Depends(require_api_key("rbac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: RBACService = Depends(get_rbac_service),
):
    t1     = T.time()
    result = await service.remove_parent(account_id=account_id, role_id=role_id, parent_role_id=dto.parent_role_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error({"action": "rbac.remove_parent.error", "role_id": role_id, "error": str(err)})
        raise err.to_http_exception()
    role = result.unwrap()
    log.info({"action": "rbac.remove_parent", "role_id": role_id, "parent": dto.parent_role_id, "time": round(T.time() - t1, 4)})
    return RoleDTO(**role.model_dump())


# ── Assignments ───────────────────────────────────────────────────────────────

@router.post("/assignments", status_code=status.HTTP_201_CREATED, response_model=AssignmentDTO)
async def assign_role(
    account_id: str,
    dto:     AssignRoleDTO,
    _:       object      = Depends(require_api_key("rbac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: RBACService = Depends(get_rbac_service),
):
    t1     = T.time()
    result = await service.assign_role(
        account_id=account_id, subject_id=dto.subject_id, role_id=dto.role_id,
        subject_type=dto.subject_type, subject_username=dto.subject_username,
        user_identifier=dto.user_identifier,
    )
    if result.is_err:
        err = result.unwrap_err()
        log.error({"action": "rbac.assign.error", "subject": dto.subject_id, "role": dto.role_id, "error": str(err)})
        raise err.to_http_exception()
    assignment = result.unwrap()
    log.info({"action": "rbac.assign", "subject": dto.subject_id, "role": dto.role_id, "time": round(T.time() - t1, 4)})
    return AssignmentDTO(**assignment.model_dump())


@router.get("/assignments", response_model=list[AssignmentDTO])
async def list_assignments(
    account_id: str,
    subject_type: str | None = None,
    subject_id: str | None = None,
    role_id: str | None = None,
    search: str = "",
    _: object = Depends(require_api_key("rbac")),
    me: DTO.UserDTO = Depends(MX.get_current_user),
    service: RBACService = Depends(get_rbac_service),
):
    result = await service.list_assignments(account_id)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    rows = []
    for assignment in result.unwrap():
        if subject_type and assignment.subject_type != subject_type.upper():
            continue
        if subject_id and assignment.subject_id != subject_id:
            continue
        if role_id and assignment.role_id != role_id:
            continue
        role = await service.get_role(account_id, assignment.role_id)
        subject_name = assignment.subject_id
        if assignment.subject_type == "USER" and service._users is not None:
            user = await service._users.find_by_id(assignment.subject_id, account_id=account_id)
            if user.is_some:
                subject_name = user.unwrap().username
        elif assignment.subject_type == "GROUP":
            group = await service._groups.find_by_id(account_id, assignment.subject_id)
            if group.is_ok and group.unwrap().is_some:
                subject_name = group.unwrap().unwrap().name
        needle = search.strip().casefold()
        role_name = role.unwrap().name if role.is_ok else assignment.role_id
        if needle and needle not in f"{subject_name} {assignment.subject_type} {role_name}".casefold():
            continue
        rows.append(AssignmentDTO(
            **assignment.model_dump(), subject_name=subject_name,
            role_name=role_name,
        ))
    return rows


@router.patch("/assignments/{assignment_id}", response_model=AssignmentDTO)
async def update_assignment(
    request: Request,
    account_id: str,
    assignment_id: str,
    dto: UpdateAssignmentDTO,
    _: object = Depends(require_api_key("rbac")),
    service: RBACService = Depends(get_rbac_service),
):
    previous = await service._assignments.find_by_id(account_id, assignment_id)
    if previous.is_err:
        raise previous.unwrap_err().to_http_exception()
    if previous.unwrap().is_some:
        request.state.authorization_audit_before = previous.unwrap().unwrap().model_dump(mode="json")
    result = await service.update_assignment(
        account_id=account_id,
        assignment_id=assignment_id,
        role_id=dto.role_id,
        subject_type=dto.subject_type,
        user_identifier=dto.user_identifier,
        subject_id=dto.subject_id,
    )
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    assignment = result.unwrap()
    request.state.authorization_audit_after = assignment.model_dump(mode="json")
    role = await service.get_role(account_id, assignment.role_id)
    subject_name = assignment.subject_id
    if assignment.subject_type == "USER":
        user = await service._users.find_by_id(assignment.subject_id, account_id=account_id)
        if user.is_some:
            subject_name = user.unwrap().username
    else:
        group = await service._groups.find_by_id(account_id, assignment.subject_id)
        if group.is_ok and group.unwrap().is_some:
            subject_name = group.unwrap().unwrap().name
    return AssignmentDTO(
        **assignment.model_dump(), subject_name=subject_name,
        role_name=role.unwrap().name if role.is_ok else assignment.role_id,
    )


@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(
    account_id: str,
    assignment_id: str,
    _: object = Depends(require_api_key("rbac")),
    me: DTO.UserDTO = Depends(MX.get_current_user),
    service: RBACService = Depends(get_rbac_service),
):
    result = await service.delete_assignment(account_id, assignment_id)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/assignments", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_role(
    account_id: str,
    dto:     UnassignRoleDTO,
    _:       object      = Depends(require_api_key("rbac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: RBACService = Depends(get_rbac_service),
):
    t1     = T.time()
    result = await service.unassign_role(account_id=account_id, subject_id=dto.subject_id, role_id=dto.role_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error({"action": "rbac.unassign.error", "subject": dto.subject_id, "role": dto.role_id, "error": str(err)})
        raise err.to_http_exception()
    log.info({"action": "rbac.unassign", "subject": dto.subject_id, "role": dto.role_id, "time": round(T.time() - t1, 4)})
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/subjects/{subject_id}/roles", status_code=status.HTTP_200_OK)
async def get_subject_roles(
    account_id: str,
    subject_id: str,
    _:          object      = Depends(require_api_key("rbac")),
    me:         DTO.UserDTO = Depends(MX.get_current_user),
    service:    RBACService = Depends(get_rbac_service),
):
    t1     = T.time()
    result = await service.get_subject_roles(account_id, subject_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error({"action": "rbac.subject_roles.error", "subject": subject_id, "error": str(err)})
        raise err.to_http_exception()
    roles = result.unwrap()
    log.info({"action": "rbac.subject_roles", "subject": subject_id, "count": len(roles), "time": round(T.time() - t1, 4)})
    return [RoleDTO(**r.model_dump()) for r in roles]


# ── Check / effective permissions ─────────────────────────────────────────────

@router.post("/check", status_code=status.HTTP_200_OK, response_model=CheckResultDTO)
async def check_permission(
    account_id: str,
    dto:     CheckPermissionDTO,
    _:       object      = Depends(require_api_key("rbac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: RBACService = Depends(get_rbac_service),
):
    t1     = T.time()
    identifier = dto.user_identifier or dto.subject_id or ""
    resolved = await service.resolve_user(account_id, identifier)
    if resolved.is_err:
        raise resolved.unwrap_err().to_http_exception()
    subject_id = resolved.unwrap().user_id
    result = await service.check_explained(account_id=account_id, subject_id=subject_id, required_permission=dto.permission)
    if result.is_err:
        err = result.unwrap_err()
        log.error({"action": "rbac.check.error", "subject": dto.subject_id, "error": str(err)})
        raise err.to_http_exception()
    has_access, matched_permission = result.unwrap()
    log.info({"action": "rbac.check", "subject": dto.subject_id, "permission": dto.permission, "result": has_access, "time": round(T.time() - t1, 4)})
    return CheckResultDTO(subject_id=subject_id, permission=dto.permission, has_access=has_access, matched_permission=matched_permission)


@router.post("/has-role", status_code=status.HTTP_200_OK, response_model=HasRoleDTO)
async def has_role(
    account_id: str,
    dto:     HasRoleCheckDTO,
    _:       object      = Depends(require_api_key("rbac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: RBACService = Depends(get_rbac_service),
):
    t1     = T.time()
    identifier = dto.user_identifier or dto.subject_id or ""
    resolved = await service.resolve_user(account_id, identifier)
    if resolved.is_err:
        raise resolved.unwrap_err().to_http_exception()
    subject_id = resolved.unwrap().user_id
    result = await service.has_role_explained(account_id=account_id, subject_id=subject_id, role_id=dto.role_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error({"action": "rbac.has_role.error", "subject": dto.subject_id, "role": dto.role_id, "error": str(err)})
        raise err.to_http_exception()
    found, path = result.unwrap()
    log.info({"action": "rbac.has_role", "subject": dto.subject_id, "role": dto.role_id, "result": found, "time": round(T.time() - t1, 4)})
    return HasRoleDTO(subject_id=subject_id, role_id=dto.role_id, has_role=found, resolution_path=path)


@router.get("/effective", response_model=EffectivePermissionsDTO)
async def get_effective_permissions_by_identifier(
    account_id: str,
    user_identifier: str = Query(..., min_length=1),
    _: object = Depends(require_api_key("rbac")),
    service: RBACService = Depends(get_rbac_service),
):
    resolved = await service.resolve_user(account_id, user_identifier)
    if resolved.is_err:
        raise resolved.unwrap_err().to_http_exception()
    subject_id = resolved.unwrap().user_id
    result = await service.get_effective_permissions_explained(account_id, subject_id)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    return EffectivePermissionsDTO(subject_id=subject_id, **result.unwrap())


@router.get("/subjects/{subject_id}/permissions", status_code=status.HTTP_200_OK, response_model=EffectivePermissionsDTO)
async def get_effective_permissions(
    account_id: str,
    subject_id: str,
    _:          object      = Depends(require_api_key("rbac")),
    me:         DTO.UserDTO = Depends(MX.get_current_user),
    service:    RBACService = Depends(get_rbac_service),
):
    t1     = T.time()
    result = await service.get_effective_permissions_explained(account_id, subject_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error({"action": "rbac.effective_perms.error", "subject": subject_id, "error": str(err)})
        raise err.to_http_exception()
    details = result.unwrap()
    perms = details["permissions"]
    log.info({"action": "rbac.effective_perms", "subject": subject_id, "count": len(perms), "time": round(T.time() - t1, 4)})
    return EffectivePermissionsDTO(subject_id=subject_id, **details)


# ── Data Discovery Endpoints ──────────────────────────────────────────────────

@router.get("/roles/list", status_code=status.HTTP_200_OK)
async def list_roles_discovery(
    account_id: str,
    _:       object      = Depends(require_admin_or_api_key("rbac")),
    service: RBACService = Depends(get_rbac_service),
):
    t1     = T.time()
    result = await service.list_roles_discovery(account_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error({"action": "rbac.list_roles_discovery.error", "error": str(err)})
        raise err.to_http_exception()
    roles = result.unwrap()
    log.info({"action": "rbac.list_roles_discovery", "role_count": len(roles), "time": round(T.time() - t1, 4)})
    return roles


@router.get("/permissions/list", status_code=status.HTTP_200_OK)
async def list_permissions_discovery(
    account_id: str,
    _:       object      = Depends(require_admin_or_api_key("rbac")),
    service: RBACService = Depends(get_rbac_service),
):
    t1 = T.time()
    # Return all available permissions (can be expanded based on your permission model)
    result = await service.list_permission_catalog(account_id)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    permissions = [{"id": permission, "name": permission} for permission in result.unwrap()]
    log.info({"action": "rbac.list_permissions_discovery", "permission_count": len(permissions), "time": round(T.time() - t1, 4)})
    return permissions
