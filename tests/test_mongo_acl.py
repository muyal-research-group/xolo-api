import pytest
import pytest_asyncio
from xoloapi.services.acl import XoloACL
import asyncio
from mongomock_motor import AsyncMongoMockClient
from motor.motor_asyncio import AsyncIOMotorClient
from xoloapi.models import GroupMember
from xoloapi.enums import PrincipalType, Permission
from typing import AsyncGenerator

from xoloapi.db.constants import CollectionNames

# --- 1. THE SETUP (Async Fixtures) ---

@pytest_asyncio.fixture
async def acl_service()->AsyncGenerator[XoloACL, None]:
    """
    Creates a fresh, in-memory ACL service for each test.
    """
    # A. Create a Mock Client (No Real DB needed)
    # client = AsyncMongoMockClient()
    # db = client["test_mictlan_db"]
    # B Create using a real mongodb service
    client  = AsyncIOMotorClient("mongodb://localhost:27018")
    # await client.drop_database("test_mictlan_db")
    db      = client["xolo_test_db"]
    for col_name in [CollectionNames.USERS_COLLECTION_NAME,
                    CollectionNames.LICENSES_COLLECTION_NAME,
                    CollectionNames.SCOPES_COLLECTION_NAME,
                    CollectionNames.SCOPE_USER_COLLECTION_NAME,
                    CollectionNames.GROUPS_COLLECTION_NAME,
                    CollectionNames.GROUP_MEMBERS_COLLECTION_NAME,
                    CollectionNames.ACCESS_POLICIES_COLLECTION_NAME,
                    CollectionNames.SECURITY_GROUPS_COLLECTION_NAME
                    ]:
        await db.drop_collection(col_name)

    # for coll_name in await db.list_collection_names():
        # await db.drop_collection(coll_name)

    service = XoloACL(db)
    
    yield service
    
    # C. Cleanup
    client.close()


@pytest.mark.asyncio
async def test_claim_and_check_ownership(acl_service: XoloACL):
    # 1. ARRANGE: Define our test data
    user_id = "u_ignacio"
    bucket_id = "bucket-photos-2026"

    # 2. ACT: Try to claim the resource
    result = await acl_service.claim_resource(user_id, bucket_id)

    # 3. ASSERT: detailed checks
    
    # Check A: Did the function return Success?
    assert result.is_ok is True, f"Claim failed: {result.unwrap_err()}"

    # Check B: Does the ACL 'check' system actually let us in?
    can_manage = await acl_service.check(user_id, bucket_id, [Permission.MANAGE])
    assert can_manage is True

    # Check C: (Optional) Verify directly in the Mock Collection
    # This proves it was actually saved to the "DB"
    saved_policy = await acl_service.policies.find_one({"resource_id": bucket_id})
    print(saved_policy)
    assert saved_policy is not None
    assert saved_policy["principal_id"] == user_id
    assert saved_policy["is_owner"] is True



@pytest.mark.asyncio
async def test_anti_theft_prevention(acl_service:XoloACL):
    """
    Scenario: Ignacio claims a bucket. Diego tries to claim it afterwards.
    Expected: Diego is rejected.
    """
    # 1. Ignacio claims it
    claim_resource_reuslt =await acl_service.claim_resource("u_ignacio", "bucket-secret-plans")
    assert claim_resource_reuslt.is_ok

    # 2. Diego tries to steal it
    result = await acl_service.claim_resource("u_diego", "bucket-secret-plans")

    # 3. Assert failure
    assert result.is_err
    
    # 4. Verify Ignacio is still the owner
    policy = await acl_service.policies.find_one({"resource_id": "bucket-secret-plans"})
    assert policy["principal_id"] == "u_ignacio"


@pytest.mark.asyncio
async def test_grant_and_revoke_workflow(acl_service:XoloACL):
    """
    Scenario: Owner grants Read access to a friend, verifies it, then revokes it.
    """
    owner = "u_mictlan"
    friend = "u_quetzal"
    resource = "folder-memories"

    # Setup
    await acl_service.claim_resource(owner, resource)

    # 1. Grant Read Access
    grant_result = await acl_service.grant(
        owner_id=owner,
        resource_id=resource,
        target_principal_id=friend,
        principal_type=PrincipalType.USER,
        permissions=[Permission.READ]
    )
    assert grant_result.is_ok is True

    # 2. Verify Access
    has_access = await acl_service.check(friend, resource, [Permission.READ])
    assert has_access is True

    # 3. Revoke Access
    revoke_result = await acl_service.revoke(
        owner_id=owner,
        resource_id=resource,
        target_principal_id=friend,
        permission=Permission.READ
    )
    assert revoke_result.is_ok is True

    # 4. Verify Access Gone
    has_access_after = await acl_service.check(friend, resource, [Permission.READ])
    assert has_access_after is False


@pytest.mark.asyncio
async def test_security_guardrails(acl_service:XoloACL):
    """
    Scenario: A random user tries to grant permissions on a folder they don't own.
    Expected: Access Denied.
    """
    owner = "u_admin"
    hacker = "u_hacker"
    resource = "system-config"

    # Admin owns the resource
    await acl_service.claim_resource(owner, resource)

    # Hacker tries to give themselves Write access
    result = await acl_service.grant(
        owner_id=hacker,
        resource_id=resource,
        target_principal_id=hacker,
        principal_type=PrincipalType.USER,
        permissions=[Permission.WRITE]
    )

    assert result.is_err


@pytest.mark.asyncio
async def test_group_inheritance_logic(acl_service:XoloACL):
    """
    Scenario: 
    1. Create a Group 'DevTeam'.
    2. Add 'Diego' to 'DevTeam'.
    3. Grant 'DevTeam' access to a folder.
    4. Check if 'Diego' (who was never explicitly added to the folder) has access.
    """
    owner      = "u_ignacio"
    member     = "u_diego"
    group_name = "DevTeam"
    resource   = "project-x-code"

    # 1. Setup Group
    group_res = await acl_service.create_group(owner_id=owner, group_name=group_name)
    assert group_res.is_ok, f"Failed to create group: {group_res.unwrap_err()}"
    group_id = group_res.unwrap()

    # print("Created Group ID:", group_id)
    # 2. Add Diego to Group
    x = await acl_service.add_member_to_group(owner_id=owner, group_id=group_id, target_user_id=member)
    assert x.is_ok, f"Failed to add member: {x.unwrap_err()}"
    # print("Added Member Result:", x)

    # 3. Claim Resource & Share with GROUP (not Diego directly)
    await acl_service.claim_resource(owner, resource)
    
    await acl_service.grant(
        owner_id=owner,
        resource_id=resource,
        target_principal_id=group_id,
        principal_type=PrincipalType.GROUP,
        permissions=[Permission.WRITE]
    )

    # 4. The Big Test: Does Diego have Write access?
    # This proves the system correctly looked up his groups.
    has_access = await acl_service.check(member, resource, [Permission.WRITE])
    assert has_access is True

    # 5. Verify non-members don't have access
    assert await acl_service.check("u_random", resource, [Permission.WRITE]) is False


@pytest.mark.asyncio
async def test_get_resources(acl_service:XoloACL):
    """
    Scenario: Verify that the dashboard view correctly lists resources owned by a user.
    """
    owner = "u_ignacio"
    other_user = "u_diego"
    resources = ["res1", "res2", "res3"]

    # Owner claims multiple resources
    for res in resources:
        x = await acl_service.claim_resource(owner, res)
        assert x.is_ok, f"Failed to claim resource {res}: {x.unwrap_err()}"
    

    group_x = await acl_service.create_group(owner, "Testers")
    assert group_x.is_ok, f"Failed to create group: {group_x.unwrap_err()}"
    group_id = group_x.unwrap()
    x = await acl_service.add_member_to_group(owner_id=owner, group_id=group_id, target_user_id=other_user)
    print("Add Member Result:", x)
    assert x.is_ok, f"Failed to add member to group: {x.unwrap_err()}"

    x = await acl_service.grant(
        owner_id            = owner,
        resource_id         = "res1",
        target_principal_id = group_id,
        principal_type      = PrincipalType.GROUP,
        permissions         = [Permission.READ]
    )
    assert x.is_ok, f"Failed to grant group access: {x.unwrap_err()}"

    view_result = await acl_service.get_user_resources(owner)
    assert view_result.is_ok, f"Failed to get dashboard view: {view_result.unwrap_err()}"
    view = view_result.unwrap()
    print("Dashboard View[Owner]:", view)


    view_result = await acl_service.get_user_resources(other_user)
    assert view_result.is_ok, f"Failed to get dashboard view: {view_result.unwrap_err()}"
    view = view_result.unwrap()
    print("Dashboard View[Other User]:", view)
    # Fetch dashboard view for owner
    # owned_resources = await acl_service.get_resources_owned_by(owner)

    # Assert that all owned resources are listed
    # assert set(owned_resources) == set(resources)


@pytest.mark.asyncio
async def test_get_groups(acl_service:XoloACL):
    """
    Scenario: Test retrieval of groups for a user.
    """
    owner      = "u_admin"
    user1      = "u_user1"
    user2      = "u_user2"
    group_name = "TeamAlpha"

    # Create Group
    group_res = await acl_service.create_group(owner, group_name)
    assert group_res.is_ok, f"Failed to create group: {group_res.unwrap_err()}"
    group_id = group_res.unwrap()

    # Add user1 and user2 to group
    add_member_res1 = await acl_service.add_member_to_group(owner, group_id, user1)
    assert add_member_res1.is_ok, f"Failed to add member1: {add_member_res1.unwrap_err()}"
    add_member_res2 = await acl_service.add_member_to_group(owner, group_id, user2)
    assert add_member_res2.is_ok, f"Failed to add member2: {add_member_res2.unwrap_err()}"

    # Retrieve groups for user1
    (groups_user1,_) = await acl_service.get_user_groups(user1)
    (groups_user2,_) = await acl_service.get_user_groups(user2)

    print("Groups for User1:", groups_user1)
    print("Groups for User2:", groups_user2)

    assert any(g.id == group_id for g in groups_user1), "User1 should be in TeamAlpha"
    assert any(g.id == group_id for g in groups_user2), "User2 should be in TeamAlpha"

@pytest.mark.asyncio
async def test_get_owned_resources(acl_service:XoloACL):
    """
    Scenario: Test retrieval of resources owned by a user.
    """
    owner = "u_owner"
    resources = ["resA", "resB", "resC"]

    # Owner claims multiple resources
    for res in resources:
        claim_res = await acl_service.claim_resource(owner, res)
        assert claim_res.is_ok, f"Failed to claim resource {res}: {claim_res.unwrap_err()}"

    # Retrieve owned resources
    result = await acl_service.get_owned_resources(user_id=owner, page=1, page_size=10)
    assert result.is_ok, f"Failed to get owned resources: {result.unwrap_err()}"
    paginated_resources = result.unwrap()
    print("Owned Resources:", paginated_resources)
@pytest.mark.asyncio
async def test_get_shared_resources(acl_service:XoloACL):
    """
    Scenario: Test retrieval of resources shared with a user.
    """
    owner      = "u_ownerx"
    user1      = "u_user2"
    editors_group_name = "Editors"
    read_only_group_name = "ReadOnly"

    shared_resource   = "shared-doc"
    # Setup: Owner claims resource  
    claim_res = await acl_service.claim_resource(owner, shared_resource)
    assert claim_res.is_ok, f"Failed to claim resource: {claim_res.unwrap_err()}"
    # Create Group 1 
    group_res = await acl_service.create_group(owner, editors_group_name)
    assert group_res.is_ok, f"Failed to create group: {group_res.unwrap_err()}"
    group_id = group_res.unwrap()
    # Create read-only group
    group_res2 = await acl_service.create_group(owner, read_only_group_name)
    assert group_res2.is_ok, f"Failed to create group: {group_res2.unwrap_err()}"
    group_id2 = group_res2.unwrap()

    # Add user1 to group
    add_member_res = await acl_service.add_member_to_group(owner, group_id, user1)
    assert add_member_res.is_ok, f"Failed to add member: {add_member_res.unwrap_err()}"

    # Add user1 to read-only group
    add_member_res2 = await acl_service.add_member_to_group(owner, group_id2, user1)
    assert add_member_res2.is_ok, f"Failed to add member: {add_member_res2.unwrap_err()}"


    # Grant WRITE and READ permission to group
    grant_res = await acl_service.grant(
        owner_id            = owner,
        resource_id         = shared_resource,
        target_principal_id = group_id,
        principal_type      = PrincipalType.GROUP,
        permissions         = [Permission.WRITE]
    )
    assert grant_res.is_ok, f"Failed to grant permission: {grant_res.unwrap_err()}"

    # Grant only READ permission to read-only group
    grant_res2 = await acl_service.grant(
        owner_id            = owner,
        resource_id         = shared_resource,
        target_principal_id = group_id2,
        principal_type      = PrincipalType.GROUP,
        permissions         = [Permission.READ]
    )
    assert grant_res2.is_ok, f"Failed to grant permission: {grant_res2.unwrap_err()}"


    # Retrieve shared resources for user1
    result = await acl_service.get_shared_resources(user_id=user1, page=1, page_size=10)
    assert result.is_ok, f"Failed to get shared resources: {result.unwrap_err()}"
    paginated_resources = result.unwrap()
    print("Shared Resources:", paginated_resources)


@pytest.mark.asyncio
async def test_check(acl_service:XoloACL):
    """
    Scenario: Test various permission checks for users and groups.
    """
    owner      = "u_owner"
    user1      = "u_user1"
    user2      = "u_user2"
    group_name = "Editors"
    resource   = "shared-doc"

    # Setup: Owner claims resource
    claim_res = await acl_service.claim_resource(owner, resource)
    assert claim_res.is_ok, f"Failed to claim resource: {claim_res.unwrap_err()}"

    # Create Group
    group_res = await acl_service.create_group(owner, group_name)
    assert group_res.is_ok, f"Failed to create group: {group_res.unwrap_err()}"
    group_id = group_res.unwrap()

    group_res2 = await acl_service.create_group(owner, f"{group_name}_2")
    assert group_res2.is_ok, f"Failed to create group: {group_res2.unwrap_err()}"
    group_id2 = group_res2.unwrap()

    # Add user1 to group
    add_member_res = await acl_service.add_member_to_group(owner, group_id, user1)
    assert add_member_res.is_ok, f"Failed to add member: {add_member_res.unwrap_err()}"
    # Add user2 to different group
    add_member_res = await acl_service.add_member_to_group(owner, group_id2, user2)
    assert add_member_res.is_ok, f"Failed to add member: {add_member_res.unwrap_err()}"

    # Grant WRITE and READ permission to group
    grant_res = await acl_service.grant(
        owner_id            = owner,
        resource_id         = resource,
        target_principal_id = group_id,
        principal_type      = PrincipalType.GROUP,
        permissions         = [Permission.WRITE,Permission.READ]
    )
    # GRant only READ permission to other group
    grant_res = await acl_service.grant(
        owner_id            = owner,
        resource_id         = resource,
        target_principal_id = group_id2,
        principal_type      = PrincipalType.GROUP,
        permissions         = [Permission.READ]
    )

    assert grant_res.is_ok, f"Failed to grant permission: {grant_res.unwrap_err()}"

    # Check Permissions
    can_user1_write     = await acl_service.check(user1, resource, [Permission.WRITE])
    can_user2_write     = await acl_service.check(user2, resource, [Permission.WRITE])
    can_user2_only_read = await acl_service.check(user2, resource, [Permission.READ,Permission.WRITE])
    can_user1_only_read = await acl_service.check(user1, resource, [Permission.READ,Permission.WRITE])
    print(can_user2_only_read, can_user1_only_read)

    assert can_user1_write is True, "User1 should have WRITE access via group."
    assert can_user2_write is False, "User2 should NOT have WRITE access."