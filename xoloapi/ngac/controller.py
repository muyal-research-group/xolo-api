import time as T
from typing import Optional
from fastapi import APIRouter, Depends, Query, Response, status
from xoloapi.log import Log

import xoloapi.config as Cfg
import xoloapi.db as DbX
import xoloapi.middleware as MX
import commonx.dto.xolo as DTO

from xoloapi.accounts.dependencies import require_existing_account
from xoloapi.middleware.apikey import require_api_key
from xoloapi.ngac.application.ngac_service import NGACService
from xoloapi.ngac.dto import (
    AssignDTO, AssociateDTO, CheckAccessDTO,
    CreateNodeDTO, RemoveAssignmentDTO,
)
from xoloapi.ngac.infrastructure.mongo_ngac_repository import MongoNGACRepository
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
    prefix="/accounts/{account_id}/ngac",
    tags=["ngac"],
    dependencies=[Depends(require_existing_account)],
)


# ── Dependency factory ────────────────────────────────────────────────────────

def get_ngac_service() -> NGACService:
    return NGACService(
        repository=MongoNGACRepository(
            db               = DbX.get_database(),
            nodes_col        = CollectionNames.NGAC_NODES_COLLECTION_NAME,
            assignments_col  = CollectionNames.NGAC_ASSIGNMENTS_COLLECTION_NAME,
            associations_col = CollectionNames.NGAC_ASSOCIATIONS_COLLECTION_NAME,
        )
    )


# ── Nodes ─────────────────────────────────────────────────────────────────────

@router.post("/nodes", status_code=status.HTTP_201_CREATED)
async def create_node(
    account_id: str,
    dto:     CreateNodeDTO,
    _:       object       = Depends(require_api_key("ngac")),
    me:      DTO.UserDTO  = Depends(MX.get_current_user),
    service: NGACService  = Depends(get_ngac_service),
):
    t1     = T.time()
    result = await service.create_node(account_id, dto, owner_id=me.key)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("ngac.create_node.error", started_at=t1, error=err, actor_user_id=me.key, node_name=dto.name, node_type=dto.node_type.value))
        raise err.to_http_exception()
    node_id = result.unwrap()
    log.info(build_log_payload("ngac.create_node", started_at=t1, actor_user_id=me.key, node_id=node_id, node_name=dto.name, node_type=dto.node_type.value))
    return {"node_id": node_id}


@router.get("/nodes", status_code=status.HTTP_200_OK)
async def list_nodes(
    account_id: str,
    node_type: Optional[str] = Query(None, description="Filter by node type"),
    _:         object        = Depends(require_api_key("ngac")),
    me:        DTO.UserDTO   = Depends(MX.get_current_user),
    service:   NGACService   = Depends(get_ngac_service),
):
    t1     = T.time()
    result = await service.list_nodes(account_id, node_type=node_type)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("ngac.list_nodes.error", started_at=t1, error=err, actor_user_id=me.key, node_type=node_type))
        raise err.to_http_exception()
    nodes = result.unwrap()
    log.info(build_log_payload("ngac.list_nodes", started_at=t1, actor_user_id=me.key, node_type=node_type, node_count=len(nodes)))
    return [n.model_dump(exclude={"account_id"}) for n in nodes]


@router.get("/nodes/{node_id}", status_code=status.HTTP_200_OK)
async def get_node(
    account_id: str,
    node_id: str,
    _:       object      = Depends(require_api_key("ngac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: NGACService = Depends(get_ngac_service),
):
    t1     = T.time()
    result = await service.get_node(account_id, node_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("ngac.get_node.error", started_at=t1, error=err, actor_user_id=me.key, node_id=node_id))
        raise err.to_http_exception()
    log.info(build_log_payload("ngac.get_node", started_at=t1, actor_user_id=me.key, node_id=node_id))
    return result.unwrap().model_dump(exclude={"account_id"})


@router.delete("/nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(
    account_id: str,
    node_id: str,
    _:       object      = Depends(require_api_key("ngac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: NGACService = Depends(get_ngac_service),
):
    t1     = T.time()
    result = await service.delete_node(account_id, node_id, requester_key=me.key, is_admin=Cfg.is_superadmin(me))
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("ngac.delete_node.error", started_at=t1, error=err, actor_user_id=me.key, node_id=node_id))
        raise err.to_http_exception()
    log.info(build_log_payload("ngac.delete_node", started_at=t1, actor_user_id=me.key, node_id=node_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Assignments ───────────────────────────────────────────────────────────────

@router.post("/assign", status_code=status.HTTP_204_NO_CONTENT)
async def assign(
    account_id: str,
    dto:     AssignDTO,
    _:       object      = Depends(require_api_key("ngac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: NGACService = Depends(get_ngac_service),
):
    t1     = T.time()
    result = await service.assign(account_id, dto, owner_id=me.key, is_admin=Cfg.is_superadmin(me))
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("ngac.assign.error", started_at=t1, error=err, actor_user_id=me.key, from_id=dto.from_id, to_id=dto.to_id))
        raise err.to_http_exception()
    log.info(build_log_payload("ngac.assign", started_at=t1, actor_user_id=me.key, from_id=dto.from_id, to_id=dto.to_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/assign", status_code=status.HTTP_204_NO_CONTENT)
async def remove_assignment(
    account_id: str,
    dto:     RemoveAssignmentDTO,
    _:       object      = Depends(require_api_key("ngac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: NGACService = Depends(get_ngac_service),
):
    t1     = T.time()
    result = await service.remove_assignment(account_id, dto, requester_key=me.key, is_admin=Cfg.is_superadmin(me))
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("ngac.remove_assignment.error", started_at=t1, error=err, actor_user_id=me.key, from_id=dto.from_id, to_id=dto.to_id))
        raise err.to_http_exception()
    log.info(build_log_payload("ngac.remove_assignment", started_at=t1, actor_user_id=me.key, from_id=dto.from_id, to_id=dto.to_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/assignments", status_code=status.HTTP_200_OK)
async def list_assignments(
    account_id: str,
    _:       object      = Depends(require_api_key("ngac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: NGACService = Depends(get_ngac_service),
):
    t1     = T.time()
    result = await service.list_assignments(account_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("ngac.list_assignments.error", started_at=t1, error=err, actor_user_id=me.key))
        raise err.to_http_exception()
    assignments = result.unwrap()
    log.info(build_log_payload("ngac.list_assignments", started_at=t1, actor_user_id=me.key, assignment_count=len(assignments)))
    return [a.model_dump(exclude={"account_id"}) for a in assignments]


# ── Associations ──────────────────────────────────────────────────────────────

@router.post("/associate", status_code=status.HTTP_204_NO_CONTENT)
async def associate(
    account_id: str,
    dto:     AssociateDTO,
    _:       object      = Depends(require_api_key("ngac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: NGACService = Depends(get_ngac_service),
):
    t1     = T.time()
    result = await service.associate(account_id, dto, owner_id=me.key, is_admin=Cfg.is_superadmin(me))
    if result.is_err:
        err = result.unwrap_err()
        log.error(
            build_log_payload(
                "ngac.associate.error",
                started_at=t1,
                error=err,
                actor_user_id=me.key,
                user_attribute_id=dto.user_attribute_id,
                object_attribute_id=dto.object_attribute_id,
                operations=dto.operations,
            )
        )
        raise err.to_http_exception()
    log.info(
        build_log_payload(
            "ngac.associate",
            started_at=t1,
            actor_user_id=me.key,
            user_attribute_id=dto.user_attribute_id,
            object_attribute_id=dto.object_attribute_id,
            operations=dto.operations,
        )
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/associate/{association_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_association(
    account_id: str,
    association_id: str,
    _:              object      = Depends(require_api_key("ngac")),
    me:             DTO.UserDTO = Depends(MX.get_current_user),
    service:        NGACService = Depends(get_ngac_service),
):
    t1     = T.time()
    result = await service.remove_association(account_id, association_id, requester_key=me.key, is_admin=Cfg.is_superadmin(me))
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("ngac.remove_association.error", started_at=t1, error=err, actor_user_id=me.key, association_id=association_id))
        raise err.to_http_exception()
    log.info(build_log_payload("ngac.remove_association", started_at=t1, actor_user_id=me.key, association_id=association_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/associations", status_code=status.HTTP_200_OK)
async def list_associations(
    account_id: str,
    _:       object      = Depends(require_api_key("ngac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: NGACService = Depends(get_ngac_service),
):
    t1     = T.time()
    result = await service.list_associations(account_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("ngac.list_associations.error", started_at=t1, error=err, actor_user_id=me.key))
        raise err.to_http_exception()
    associations = result.unwrap()
    log.info(build_log_payload("ngac.list_associations", started_at=t1, actor_user_id=me.key, association_count=len(associations)))
    return [a.model_dump(exclude={"account_id"}) for a in associations]


# ── Access check ──────────────────────────────────────────────────────────────

@router.post("/check", status_code=status.HTTP_200_OK)
async def check_access(
    account_id: str,
    dto:     CheckAccessDTO,
    _:       object      = Depends(require_api_key("ngac")),
    me:      DTO.UserDTO = Depends(MX.get_current_user),
    service: NGACService = Depends(get_ngac_service),
):
    t1     = T.time()
    result = await service.check_access(account_id, dto)
    if result.is_err:
        err = result.unwrap_err()
        log.error(
            build_log_payload(
                "ngac.check.error",
                started_at=t1,
                error=err,
                actor_user_id=me.key,
                user_id=dto.user_id,
                object_id=dto.object_id,
                operation=dto.operation,
            )
        )
        raise err.to_http_exception()
    decision = result.unwrap()
    log.info(
        build_log_payload(
            "ngac.check",
            started_at=t1,
            actor_user_id=me.key,
            user_id=dto.user_id,
            object_id=dto.object_id,
            operation=dto.operation,
            allowed=decision.allowed,
            reason=decision.reason,
        )
    )
    return decision.model_dump()


# ── Data Discovery Endpoints ──────────────────────────────────────────────────

@router.get("/nodes/list", status_code=status.HTTP_200_OK)
async def list_nodes_discovery(
    account_id: str,
    node_type: Optional[str] = Query(None, description="Filter by node type"),
    _:         object        = Depends(require_api_key("ngac")),
    service:   NGACService   = Depends(get_ngac_service),
):
    t1     = T.time()
    result = await service.list_nodes(account_id, node_type=node_type)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("ngac.list_nodes_discovery.error", started_at=t1, error=err, node_type=node_type))
        raise err.to_http_exception()
    nodes = result.unwrap()
    log.info(build_log_payload("ngac.list_nodes_discovery", started_at=t1, node_type=node_type, node_count=len(nodes)))
    return [{"id": n.node_id, "name": n.name, "type": n.node_type} for n in nodes]


@router.get("/assignments/list", status_code=status.HTTP_200_OK)
async def list_assignments_discovery(
    account_id: str,
    _:       object      = Depends(require_api_key("ngac")),
    service: NGACService = Depends(get_ngac_service),
):
    t1     = T.time()
    result = await service.list_assignments(account_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("ngac.list_assignments_discovery.error", started_at=t1, error=err))
        raise err.to_http_exception()
    assignments = result.unwrap()
    log.info(build_log_payload("ngac.list_assignments_discovery", started_at=t1, assignment_count=len(assignments)))
    return [{"id": a.assignment_id, "child": a.child_node_id, "parent": a.parent_node_id} for a in assignments]


@router.get("/associations/list", status_code=status.HTTP_200_OK)
async def list_associations_discovery(
    account_id: str,
    _:       object      = Depends(require_api_key("ngac")),
    service: NGACService = Depends(get_ngac_service),
):
    t1     = T.time()
    result = await service.list_associations(account_id)
    if result.is_err:
        err = result.unwrap_err()
        log.error(build_log_payload("ngac.list_associations_discovery.error", started_at=t1, error=err))
        raise err.to_http_exception()
    associations = result.unwrap()
    log.info(build_log_payload("ngac.list_associations_discovery", started_at=t1, association_count=len(associations)))
    return [{"id": a.association_id, "user_attr": a.user_attribute_id, "object_attr": a.object_attribute_id, "operations": a.operations} for a in associations]
