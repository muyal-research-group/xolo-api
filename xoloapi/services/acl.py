import math

from motor.motor_asyncio import AsyncIOMotorDatabase
from option import Err, Ok

import commonx.dto.xolo as DTO
from xoloapi.acl.application.acl_service import ACLService
from xoloapi.groups.application.group_service import GroupService
from xoloapi.acl.domain.value_objects import PrincipalType
from xoloapi.acl.infrastructure.mongo_resource_policy_repository import MongoResourcePolicyRepository
from xoloapi.groups.infrastructure.mongo_security_group_repository import MongoSecurityGroupRepository
from xoloapi.db.constants import CollectionNames


class XoloACL:
    """Compatibility adapter over the structured ACL module."""

    def __init__(self, db: AsyncIOMotorDatabase, account_id: str):
        self.db = db
        self.account_id = account_id
        self.policy_repo = MongoResourcePolicyRepository(
            db=db,
            collection_name=CollectionNames.ACL_RESOURCE_POLICIES_COLLECTION_NAME,
        )
        self.group_repo = MongoSecurityGroupRepository(
            db=db,
            groups_col=CollectionNames.ACL_GROUPS_COLLECTION_NAME,
            members_col=CollectionNames.ACL_GROUP_MEMBERS_COLLECTION_NAME,
        )
        self.acl_service = ACLService(policy_repo=self.policy_repo, group_repo=self.group_repo)
        self.group_service = GroupService(repo=self.group_repo)

        self.policies = self.policy_repo.col
        self.groups = self.group_repo.groups
        self.members = self.group_repo.members
        self.users = db[CollectionNames.USERS_COLLECTION_NAME]

    async def check(self, user_id: str, resource_id: str, required_permissions: list[str]) -> bool:
        result = await self.acl_service.check(
            account_id=self.account_id,
            user_id=user_id,
            resource_id=resource_id,
            permissions=[str(getattr(permission, "value", permission)) for permission in required_permissions],
        )
        return result.unwrap_or(False)

    async def claim_resource(self, owner_id: str, resource_id: str):
        return await self.acl_service.claim_resource(account_id=self.account_id, user_id=owner_id, resource_id=resource_id)

    async def grant(self, owner_id: str, resource_id: str, target_principal_id: str, principal_type, permissions: list[str]):
        mapped_type = PrincipalType(str(getattr(principal_type, "value", principal_type)).upper())
        normalized_permissions = [str(getattr(permission, "value", permission)) for permission in permissions]
        return await self.acl_service.grant(
            account_id=self.account_id,
            caller_id=owner_id,
            resource_id=resource_id,
            principal_id=target_principal_id,
            principal_type=mapped_type,
            permissions=normalized_permissions,
        )

    async def revoke(self, owner_id: str, resource_id: str, target_principal_id: str, permission):
        return await self.acl_service.revoke(
            account_id=self.account_id,
            caller_id=owner_id,
            resource_id=resource_id,
            principal_id=target_principal_id,
            permissions=[str(getattr(permission, "value", permission))],
        )

    async def create_group(self, owner_id: str, group_name: str, description: str = ""):
        return await self.group_service.create_group(account_id=self.account_id, owner_id=owner_id, name=group_name, description=description)

    async def delete_group(self, owner_id: str, group_id: str):
        return await self.group_service.delete_group(account_id=self.account_id, caller_id=owner_id, group_id=group_id)

    async def add_member_to_group(self, owner_id: str, group_id: str, target_user_id: str):
        return await self.group_service.add_members(account_id=self.account_id, caller_id=owner_id, group_id=group_id, user_ids=[target_user_id])

    async def remove_member_from_group(self, owner_id: str, group_id: str, target_user_id: str):
        return await self.group_service.remove_members(account_id=self.account_id, caller_id=owner_id, group_id=group_id, user_ids=[target_user_id])

    async def get_user_groups(self, user_id: str):
        groups_result = await self.group_repo.find_groups_for_user(self.account_id, user_id)
        if groups_result.is_err:
            return [], {}

        group_dtos = []
        group_map = {}
        for group in groups_result.unwrap():
            is_member = (await self.group_repo.is_member(self.account_id, group.group_id, user_id)).unwrap_or(False)
            if not group.is_owned_by(user_id) and not is_member:
                continue
            role = "owner" if group.is_owned_by(user_id) else "member"
            group_dtos.append(DTO.GroupDetailDTO(id=group.group_id, name=group.name, my_role=role))
            group_map[group.group_id] = group.name
        return group_dtos, group_map

    async def get_owned_resources(self, user_id: str, page: int = 1, page_size: int = 10):
        result = await self.policy_repo.find_owned_by(self.account_id, user_id, page, page_size)
        if result.is_err:
            return Err(result.unwrap_err())
        policies, total_count = result.unwrap()
        items = [
            DTO.ResourceDetailDTO(
                resource_id=policy.resource_id,
                permissions=[perm.value for perm in policy.effective_permissions([user_id])],
                access_source="Owner",
            )
            for policy in policies
        ]
        total_pages = math.ceil(total_count / page_size) if page_size > 0 else 0
        return Ok(
            DTO.PaginatedResponseDTO[DTO.ResourceDetailDTO](
                items=items,
                total_count=total_count,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            )
        )

    async def get_shared_resources(self, user_id: str, page: int = 1, page_size: int = 10):
        _, group_map = await self.get_user_groups(user_id)
        principal_ids = [user_id] + list(group_map.keys())
        result = await self.policy_repo.find_shared_with(self.account_id, principal_ids, [], page, page_size)
        if result.is_err:
            return Err(result.unwrap_err())
        policies, total_count = result.unwrap()

        items = []
        for policy in policies:
            source = "Direct"
            for grant in policy.grants:
                if grant.principal.id in group_map:
                    source = f"Group: {group_map[grant.principal.id]}"
                    break
            items.append(
                DTO.ResourceDetailDTO(
                    resource_id=policy.resource_id,
                    permissions=[perm.value for perm in policy.effective_permissions(principal_ids)],
                    access_source=source,
                )
            )

        total_pages = math.ceil(total_count / page_size) if page_size > 0 else 0
        return Ok(
            DTO.PaginatedResponseDTO[DTO.ResourceDetailDTO](
                items=items,
                total_count=total_count,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            )
        )

    async def get_user_resources(self, user_id: str, owned_page: int = 1, owned_page_size: int = 10, shared_page: int = 1, shared_page_size: int = 10):
        groups, _ = await self.get_user_groups(user_id)
        owned_res = await self.get_owned_resources(user_id, owned_page, owned_page_size)
        if owned_res.is_err:
            return Err(owned_res.unwrap_err())
        shared_res = await self.get_shared_resources(user_id, shared_page, shared_page_size)
        if shared_res.is_err:
            return Err(shared_res.unwrap_err())

        owned_resources = owned_res.unwrap()
        shared_resources = shared_res.unwrap()
        filtered_shared_resources = DTO.PaginatedResponseDTO(
            items=[],
            total_count=0,
            page=shared_page,
            page_size=shared_page_size,
            total_pages=0,
        )
        for shared_resource in shared_resources.items:
            if not any(owned.resource_id == shared_resource.resource_id for owned in owned_resources.items):
                filtered_shared_resources.items.append(shared_resource)
        filtered_shared_resources.total_count = len(filtered_shared_resources.items)
        filtered_shared_resources.total_pages = math.ceil(filtered_shared_resources.total_count / shared_page_size) if shared_page_size > 0 else 0

        return Ok(
            DTO.UsersResourcesDTO(
                user_id=user_id,
                groups=groups,
                owned_resources=owned_resources,
                shared_resources=filtered_shared_resources,
            )
        )
