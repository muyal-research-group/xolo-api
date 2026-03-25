from xoloapi.dto import acl
from xoloapi.services.acl import XoloACL
from fastapi import Depends,status,Query
from fastapi.routing import APIRouter
import time as T

import xoloapi.db as DbX
import xoloapi.config as Cfg
import xoloapi.middleware as MX
# 
import commonx.dto.xolo as DTO
import commonx.enums.xolo as Enums
import commonx.errors as EX

from xolo.log import Log

log            = Log(
        name                   = __name__,
        console_handler_filter = lambda x: True,
        interval               = Cfg.XOLO_LOG_INTERVAL,
        when                   = Cfg.XOLO_LOG_WHEN,
        path                   = Cfg.XOLO_LOG_PATH
)
router = APIRouter(
    prefix="/acl",
    tags=["acl"],
)

def get_acl():
    return XoloACL(
        db= DbX.get_database()
    )

@router.get("/resources", status_code=status.HTTP_200_OK)
async def get_resources(
    acl: XoloACL = Depends(get_acl),
    owned_page: int = Query(1, ge=1, description="Page number for owned resources pagination"),
    owned_page_size: int = Query(10, ge=0, description="Page size for owned resources pagination"),
    shared_page: int = Query(1, ge=1, description="Page number for shared resources pagination"),
    shared_page_size: int = Query(10, ge=0, description="Page size for shared resources pagination"),
    me:DTO.UserDTO = Depends(MX.get_current_user)
):
    t1 = T.time()
    # if owned_page < 1:
        # owned_page = 1
    # if shared_page < 1:
        # shared_page = 1

    result = await acl.get_user_resources(
        user_id  = me.key,
        owned_page = owned_page,
        owned_page_size = owned_page_size,
        shared_page = shared_page,
        shared_page_size = shared_page_size
    )
    if result.is_err:
        log.error({
            "action":"acl.get_user_dashboard_view.error",
            "user_id":me.key,
            "error": str(result.unwrap_err())
        })
        raise result.unwrap_err().to_http_exception()
    
    t2 = T.time()
    log.info({
        "action":"acl.get_user_dashboard_view",
        "user_id":me.key,
        "time":round(t2-t1,4)
    })
    return result.unwrap()




@router.post("/groups", status_code=status.HTTP_201_CREATED)
async def create_group(
    # name: str,
    dto: DTO.CreateGroupDTO,
    acl: XoloACL = Depends(get_acl),
    me:DTO.UserDTO = Depends(MX.get_current_user)
):
    t1 = T.time()
    result = await acl.create_group(
        owner_id= me.key,
        group_name=dto.name,
        description=dto.description
    )
    if result.is_err:
        log.error({
            "action":"acl.create_group.error",
            "group_name":dto.name,
            "error": str(result.unwrap_err())
        })
        raise result.unwrap_err().to_http_exception()
    
    group_id = result.unwrap()

    t2 = T.time()
    log.info({
        "action":"acl.create_group",
        "group_id":group_id,
        "group_name":dto.name,
        "time":round(t2-t1,4)
    })
    return {"group_id": group_id}
    # return {"group_id": result.unwrap()}

@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: str,
    acl: XoloACL = Depends(get_acl),
    me:DTO.UserDTO = Depends(MX.get_current_user)
):
    t1 = T.time()
    result = await acl.delete_group(
        owner_id= me.key,
        group_id=group_id
    )
    if result.is_err:
        log.error({
            "action":"acl.delete_group.error",
            "group_id":group_id,
            "error": str(result.unwrap_err())
        })
        raise result.unwrap_err().to_http_exception()
    
    t2 = T.time()
    log.info({
        "action":"acl.delete_group",
        "group_id":group_id,
        "time":round(t2-t1,4)
    })
    return


@router.post("/groups/{group_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def add_member_to_group(
    group_id: str,
    dto: DTO.AddOrDeleteMembersToGroupDTO,
    acl: XoloACL = Depends(get_acl),
    me:DTO.UserDTO = Depends(MX.get_current_user)
):
    t1 = T.time()
    for member_id in dto.members:
        result = await acl.add_member_to_group(
            owner_id  = me.key,
            group_id  = group_id,
            target_user_id = member_id
        )
        if result.is_err:
            log.error({
                "action":"acl.add_member_to_group.error",
                "group_id":group_id,
                "member_id":member_id,
                "error": str(result.unwrap_err())
            })
            raise result.unwrap_err().to_http_exception()
    
    t2 = T.time()
    log.info({
        "action":"acl.add_member_to_group",
        "group_id":group_id,
        "members":dto.members,
        "time":round(t2-t1,4)
    })
    return  


@router.delete("/groups/{group_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member_from_group(
    group_id: str,
    # member_id: str,
    dto:DTO.AddOrDeleteMembersToGroupDTO,
    acl: XoloACL = Depends(get_acl),
    me:DTO.UserDTO = Depends(MX.get_current_user)
):
    t1 = T.time()
    for member_id in dto.members:
        result = await acl.remove_member_from_group(
            owner_id  = me.key,
            group_id  = group_id,
            target_user_id = member_id
        )
        if result.is_err:
            log.error({
                "action":"acl.remove_member_from_group.error",
                "group_id":group_id,
                "member_id":member_id,
                "error": str(result.unwrap_err())
            })
            raise result.unwrap_err().to_http_exception()
    
    t2 = T.time()
    log.info({
        "action":"acl.remove_member_from_group",
        "group_id":group_id,
        "member_id":member_id,
        "time":round(t2-t1,4)
    })
    return


@router.post("/grant",status_code=status.HTTP_204_NO_CONTENT)
async def grant_permission(
    dto: DTO.GrantOrRevokePermissionDTO,
    acl: XoloACL = Depends(get_acl),
    me:DTO.UserDTO = Depends(MX.get_current_user)
):
    t1 = T.time()
    result = await acl.grant(
        owner_id            = me.key,
        resource_id         = dto.resource_id,
        target_principal_id = dto.principal_id,
        principal_type      = Enums.PrincipalType(dto.principal_type.upper().strip()),
        permissions         = dto.permissions,
    # is_owner            = dto.is_owner
    )
    if result.is_err:
        log.error({
            "action":"acl.grant_permission.error",
            "principal":dto.principal_id,
            "resource":dto.resource_id,
            "permissions":dto.permissions,
            "error": str(result.unwrap_err())
        })
        raise result.unwrap_err().to_http_exception()
    
    t2 = T.time()
    log.info({
        "action":"acl.grant_permission",
        "principal":dto.principal_id,
        "resource":dto.resource_id,
        "permissions":dto.permissions,
        "time":round(t2-t1,4)
    })
    return

@router.post("/claim",status_code=status.HTTP_204_NO_CONTENT)
async def claim_ownership(
    dto: DTO.ClaimResourceDTO,
    acl: XoloACL = Depends(get_acl),
    me:DTO.UserDTO = Depends(MX.get_current_user)
):
    t1 = T.time()
    result = await acl.claim_resource(
        owner_id     = me.key,
        resource_id = dto.resource_id
    )
    if result.is_err:
        log.error({
            "action":"acl.claim_ownership.error",
            "resource":dto.resource_id,
            "error": str(result.unwrap_err())
        })
        raise result.unwrap_err().to_http_exception()
    t2 = T.time()
    log.info({
        "action":"acl.claim_ownership",
        "resource":dto.resource_id,
        "time":round(t2-t1,4)
    })
    return

@router.delete("/revoke",status_code=status.HTTP_204_NO_CONTENT)
async def revoke_permission(
    dto: DTO.GrantOrRevokePermissionDTO,
    acl: XoloACL = Depends(get_acl),
    me:DTO.UserDTO = Depends(MX.get_current_user)
):
    t1 = T.time()
    for permission in dto.permissions:
        result = await acl.revoke(
            owner_id            = me.key,
            resource_id         = dto.resource_id,
            target_principal_id = dto.principal_id,
            permission          = permission
        )
        if result.is_err:
            log.error({
                "action":"acl.revoke_permission.error",
                "principal":dto.principal_id,
                "resource":dto.resource_id,
                "permission":permission,
                "error": str(result.unwrap_err())
            })
            raise result.unwrap_err().to_http_exception()
    
    t2 = T.time()
    log.info({
        "action":"acl.revoke_permission",
        "principal":dto.principal_id,
        "resource":dto.resource_id,
        "permissions":dto.permissions,
        "time":round(t2-t1,4)
    })
    return


@router.post("/check",status_code=status.HTTP_200_OK)
async def check_permission(
    dto: DTO.CheckDTO,
    acl: XoloACL = Depends(get_acl),
    me:DTO.UserDTO = Depends(MX.get_current_user)
):
    t1 = T.time()
    for permission in dto.permissions:
        has_permission = await acl.check(
            user_id     = me.key,
            resource_id = dto.resource_id,
            required_permissions  = [permission]
        )
        if not has_permission:
            raise EX.AccessDenied(raw_detail="You do not have the required permission.").to_http_exception()
    t2 = T.time()
    log.info({
        "action":"acl.check_permission",
        "actor":me.key,
        "resource":dto.resource_id,
        "permissions":dto.permissions,
        "result":has_permission,
        "time":round(t2-t1,4)
    })
    return {"has_permission": has_permission}