from typing import List, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase
from option import Result, Ok, Err
import uuid
import xoloapi.errors as EX
import xoloapi.dto as DTO
import math 
from commonx.models.xolo import AccessPolicy, SecurityGroup, GroupMember
from commonx.enums.xolo import PrincipalType, Permission
from xoloapi.db.constants import CollectionNames

class XoloACL:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        # Define collections
        self.policies = db[CollectionNames.ACCESS_POLICIES_COLLECTION_NAME]
        self.groups   = db[CollectionNames.SECURITY_GROUPS_COLLECTION_NAME]
        self.members  = db[CollectionNames.GROUP_MEMBERS_COLLECTION_NAME]
        self.users    = db[CollectionNames.USERS_COLLECTION_NAME]



    # ==========================================
    # 1. THE CORE CHECK ENGINE
    # ==========================================

    async def check(self, user_id: str, resource_id: str, required_permissions: List[str]) -> bool:
        """
        Determines if 'user_id' has ALL the permissions in 'required_permissions'.
        It aggregates permissions from the user and all their groups.
        """
        # Step A: Find all groups this user belongs to
        group_ids = await self._get_user_group_ids(user_id)

        # Step B: Build the list of Principals to check
        principals_to_check = [user_id] + group_ids

        # Step C: Database Query - "Distinct"
        # We ask MongoDB: "Give me a list of every unique permission string found
        # in ALL policies belonging to these principals for this resource."
        granted_permissions = await self.policies.distinct(
            "permissions", 
            {
                "resource_id": resource_id,
                "principal_id": {"$in": principals_to_check}
            }
        )

        # Step D: Set Logic (All or Nothing)
        # Convert lists to sets for efficient comparison
        required_set = set(required_permissions)
        granted_set = set(granted_permissions)

        # Returns True only if every item in required_set exists in granted_set
        return required_set.issubset(granted_set)



    async def _get_user_group_ids(self, user_id: str) -> List[str]:
        """Helper to get list of Group IDs a user is a member of."""
        cursor = self.members.find({"user_id": user_id}, {"group_id": 1})
        group_ids = []
        async for doc in cursor:
            group_ids.append(doc["group_id"])
        return group_ids

    # ==========================================
    # 2. RESOURCE CLAIMING (Anti-Theft)
    # ==========================================

    async def claim_resource(self, owner_id: str, resource_id: str) -> Result[bool, EX.XError]:
        """
        Attempts to become the MAIN OWNER of a resource.
        Fails if the resource is already owned by someone else.
        """
        # 1. Atomic Check: Is there already an owner?
        existing_owner = await self.policies.find_one({
            "resource_id": resource_id,
            "is_owner": True
        })

        if existing_owner:
            if existing_owner["principal_id"] == owner_id:
                return Ok(True) # Idempotent: You are already the owner
            
            return Err(EX.FailedToClaimResource(raw_detail="Resource is already owned by another user."))

        # 2. Create the Owner Policy
        policy = AccessPolicy(
            resource_id    = resource_id,
            principal_id   = owner_id,
            principal_type = PrincipalType.USER,
            permissions    = [Permission.MANAGE, Permission.READ, Permission.WRITE, Permission.DELETE],
            is_owner       = True
        )
        
        # Insert (exclude 'id' so Mongo generates it)
        await self.policies.insert_one(policy.model_dump(by_alias=True, exclude={"id"}))
        return Ok(True)

    # ==========================================
    # 3. GRANTING ACCESS (Sharing)
    # ==========================================

    async def grant(self, 
                    owner_id: str, 
                    resource_id: str, 
                    target_principal_id: str, 
                    principal_type: PrincipalType, 
                    permissions: List[str]) -> Result[bool, EX.XError]:
        """
        Grants permissions to a User or Group.
        Securely checks if 'actor_id' has 'sys:manage' first.
        """
        # 1. Security Check: Does the actor manage this resource?
        can_manage = await self.check(owner_id, resource_id, [Permission.MANAGE])
        if not can_manage:
            return Err(EX.AccessDenied(raw_detail="You do not have permission to share this resource."))

        # 2. Upsert: Update existing policy or create new one
        # If a policy already exists for this (Resource + User), we just add the new permissions.
        await self.policies.update_one(
            {
                "resource_id": resource_id,
                "principal_id": target_principal_id,
                "principal_type": principal_type
            },
            {
                "$addToSet": {"permissions": {"$each": permissions}},
                "$setOnInsert": {"is_owner": False} # Ensure they don't become owner by accident
            },
            upsert=True
        )
        return Ok(True)

    # ==========================================
    # 4. REVOKING ACCESS
    # ==========================================

    async def revoke(self, owner_id: str, resource_id: str, target_principal_id: str, permission: str) -> Result[bool, EX.XError]:
        """
        Removes a specific permission.
        """
        # 1. Permission Check
        # Allow self-revocation (Leaving a shared folder) OR Manager revocation
        if owner_id != target_principal_id:
            can_manage = await self.check(owner_id, resource_id, [Permission.MANAGE])
            if not can_manage:
                return Err(EX.AccessDenied(raw_detail="You do not have permission to revoke this access."))

        # 2. Prevent removing the last owner via this method (Safety)
        if permission == Permission.MANAGE:
             is_target_owner = await self.policies.find_one({
                 "resource_id": resource_id, 
                 "principal_id": target_principal_id,
                 "is_owner": True
             })
             if is_target_owner:
                 # Check if they are the ONLY owner
                 owner_count = await self.policies.count_documents({"resource_id": resource_id, "is_owner": True})
                 if owner_count <= 1:
                     return Err(EX.FailedToRemoveOwner(raw_detail="Cannot remove the last owner of the resource."))

        # 3. Atomically remove the permission
        await self.policies.update_one(
            {
                "resource_id": resource_id,
                "principal_id": target_principal_id
            },
            {"$pull": {"permissions": permission}}
        )
        
        return Ok(True)

    # ==========================================
    # 5. GROUP MANAGEMENT
    # ==========================================

    async def create_group(self, owner_id: str, group_name: str, description: str = "") -> Result[str, EX.XError]:
        """Creates a new Security Group and makes the creator an admin member."""
        
        # 1. Create Group Document
        # Generate a readable ID or use UUID
        uuid_part = uuid.uuid4().hex[:8]
        # owner_id[-4:]  # Simple uniqueness based on owner_id
        group_id = f"g-{group_name.lower().replace(' ', '-')}-{uuid_part}"
        
        exists = await self.groups.find_one({"name": group_name})
        if exists:
            return Err(EX.AlreadyExists(entity="Group",id=group_name,raw_detail="A group with this name already exists."))

        group = SecurityGroup(
            group_id    = group_id,
            name        = group_name,
            owner_id    = owner_id,
            description = description
        )
        
        try:
            await self.groups.insert_one(group.model_dump(by_alias=True))
        except Exception as e:
            return Err(EX.CreationError(entity="Group", raw_detail=str(e)))

        # 2. Add owner to the group (Self-Join)
        member_link = GroupMember(
            group_id=group_id,
            user_id=owner_id,
            role_in_group="owner"
        )
        await self.members.insert_one(member_link.model_dump(exclude={"id"}))
        
        return Ok(group_id)

    async def delete_group(self, owner_id: str, group_id: str) -> Result[bool, EX.XError]:
        """Deletes a group. Only the Group Owner can do this."""
        
        # 1. Verify Group Ownership
        group = await self.groups.find_one({"group_id": group_id})
        if not group:
            return Err(EX.NotFound(entity="group"))
        
        if group["owner_id"] != owner_id:
            return Err(EX.AccessDenied(raw_detail="You do not have permission to delete this group."))

        # 2. Delete Group Document
        await self.groups.delete_one({"group_id": group_id})

        # 3. Delete all Membership Links
        await self.members.delete_many({"group_id": group_id})

        return Ok(True)


    async def add_member_to_group(self, owner_id: str, group_id: str, target_user_id: str) -> Result[bool, EX.XError]:
        """Adds a user to a group. Only the Group Owner can do this."""
        
        # 1. Verify Group Ownership
        group = await self.groups.find_one({"group_id": group_id})
        # print(group)
        if not group:
            return Err(EX.NotFound(entity="group"))
        
        if group["owner_id"] != owner_id:
            return Err(EX.AccessDenied(raw_detail="You do not have permission to add members to this group."))

        # 2. Check if already a member (Idempotency)
        exists = await self.members.find_one({"group_id": group_id, "user_id": target_user_id})
        if exists:
            return Ok(True) 

        # 3. Create Link
        link = GroupMember(
            group_id=group_id, 
            user_id=target_user_id,
            role_in_group="member"
        )
        await self.members.insert_one(link.model_dump(exclude={"id"}))
        
        return Ok(True)
    
    async def remove_member_from_group(self, owner_id: str, group_id: str, target_user_id: str) -> Result[bool, EX.XError]:
        """Removes a user from a group."""
        
        group = await self.groups.find_one({"group_id": group_id})
        if not group: return Err(EX.NotFound(entity="group"))
        # Allow user to leave, OR owner to kick
        if owner_id != target_user_id and group["owner_id"] != owner_id:
            return Err(EX.AccessDenied(raw_detail="You do not have permission to remove this member from the group."))

        await self.members.delete_one({"group_id": group_id, "user_id": target_user_id})
        return Ok(True)
    

    # ==========================================
    # 6. DASHBOARD / VIEWS
    # ==========================================
    async def get_user_groups(self, user_id: str) -> Tuple[List[DTO.GroupDetailDTO], dict]:
        """
        Helper: Gets all groups a user belongs to. 
        Returns (List of GroupDTOs, Dict mapping group_id -> group_name)
        """
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$lookup": {
                "from": "security_groups",
                "localField": "group_id",
                "foreignField": "group_id", # Ensure this matches your Schema (usually _id)
                "as": "group_info"
            }},
            {"$unwind": "$group_info"},
            {"$project": {
                "group_id": 1,
                "role_in_group": 1,
                "group_name": "$group_info.name"
            }}
        ]
        
        my_groups = []
        group_map = {} 

        async for doc in self.members.aggregate(pipeline):
            g_id = doc["group_id"]
            g_name = doc["group_name"]
            my_groups.append(
                DTO.GroupDetailDTO(
                    id=g_id, name=g_name, my_role=doc["role_in_group"]
                )
            )
            group_map[g_id] = g_name


        return my_groups, group_map
    

    async def get_owned_resources(
        self, user_id: str, page: int = 1, page_size: int = 10
    ) -> Result[DTO.PaginatedResponseDTO[DTO.ResourceDetailDTO], Exception]:
        """
        Fetches only the resources owned by the user with pagination.
        """
        try:
            query = {
                "principal_id": user_id,
                "is_owner": True
            }
            
            # 1. Count Total
            total_count = await self.policies.count_documents(query)
            
            # 2. Fetch Page
            skip = (page - 1) * page_size
            cursor = self.policies.find(query).skip(skip).limit(page_size)
            
            items = []
            async for policy in cursor:
                items.append(DTO.ResourceDetailDTO(
                    resource_id=policy["resource_id"],
                    permissions=policy["permissions"],
                    access_source="Owner"
                ))

            # 3. Calculate Pages
            total_pages = math.ceil(total_count / page_size) if page_size > 0 else 0
            
            return Ok(DTO.PaginatedResponseDTO[DTO.ResourceDetailDTO](
                items=items,
                total_count=total_count,
                page=page,
                page_size=page_size,
                total_pages=total_pages
            ))
        except Exception as e:
            return Err(e)

    async def get_shared_resources(
        self, user_id: str, page: int = 1, page_size: int = 10
    ) -> Result[DTO.PaginatedResponseDTO[DTO.ResourceDetailDTO], Exception]:
        """
        Fetches resources shared with the user (Direct or via Group).
        Excludes resources the user owns.
        """
        try:
            # Step A: Need Group IDs first to build the query
            _, group_map = await self.get_user_groups(user_id)
            group_ids = list(group_map.keys())
            
            principals_to_check = [user_id] + group_ids

            # Step B: The Query
            # Match: (My ID OR My Group ID) AND (Not Owner)
            query = {
                "principal_id": {"$in": principals_to_check},
                "is_owner": False # Explicitly exclude owned items
            }

            # 1. Count Total
            total_count = await self.policies.count_documents(query)

            # 2. Fetch Page
            skip = (page - 1) * page_size
            cursor = self.policies.find(query).skip(skip).limit(page_size)

            items = []
            async for policy in cursor:
                principal = policy["principal_id"]
                
                # Determine Source Label
                source = "Direct"
                if principal in group_map:
                    source = f"Group: {group_map[principal]}"

                items.append(DTO.ResourceDetailDTO(
                    resource_id=policy["resource_id"],
                    permissions=policy["permissions"],
                    access_source=source
                ))

            # 3. Calculate Pages
            total_pages = math.ceil(total_count / page_size) if page_size > 0 else 0

            return Ok(DTO.PaginatedResponseDTO[DTO.ResourceDetailDTO](
                items=items,
                total_count=total_count,
                page=page,
                page_size=page_size,
                total_pages=total_pages
            ))
        except Exception as e:
            return Err(e)

    async def get_user_resources(
        self,
        user_id: str,
        owned_page: int = 1,
        owned_page_size: int = 10,
        shared_page: int = 1,
        shared_page_size: int = 10
    ) -> Result[DTO.UsersResourcesDTO, Exception]:
        """
        Aggregates everything using the pagination helpers.
        """
        try:
            # 1. Get Groups (Not typically paginated in dashboard view, usually small list)
            my_groups, _ = await self.get_user_groups(user_id)

            # 2. Get Owned (Paginated)
            owned_res = await self.get_owned_resources(user_id, owned_page, owned_page_size)
            if owned_res.is_err: return Err(owned_res.unwrap_err())
            
            # 3. Get Shared (Paginated)
            shared_res = await self.get_shared_resources(user_id, shared_page, shared_page_size)
            if shared_res.is_err: return Err(shared_res.unwrap_err())

            # 4. Construct Final DTO
            # Note: The dashboard DTO needs to be updated to accept PaginatedResponseDTO 
            # instead of raw Lists for owned/shared
            owned_resources = owned_res.unwrap()
            shared_resources = shared_res.unwrap()

            filtered_shared_resources = DTO.PaginatedResponseDTO(items=[], total_count=0, page=shared_page, page_size=shared_page_size, total_pages=0)
            for shared_resource in shared_resources.items:
                # Exclude resources that are also owned
                if not any(owned.resource_id == shared_resource.resource_id for owned in owned_resources.items):
                    filtered_shared_resources.items.append(shared_resource)
            filtered_shared_resources.total_count = len(filtered_shared_resources.items)


            return Ok(DTO.UsersResourcesDTO(
                user_id=user_id,
                groups=my_groups,
                owned_resources=owned_resources,
                shared_resources=filtered_shared_resources
            ))
        except Exception as e:
            return Err(e)