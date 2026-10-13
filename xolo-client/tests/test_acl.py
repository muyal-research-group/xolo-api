import pytest
from xolo.acl.acl import Acl
import os

@pytest.fixture()
def acl():
    output_path = os.environ.get("XOLO_OUTPUT_PATH", "/xolo")
    filename    = "xolotest.enc"
    # fullpath    = "{}/{}".format(output_path,filename)
    acl = Acl.load_or_create(
        output_path = output_path,
        key         = "ceb2d1e79b1edefa82ffa54b94b5bf911b534a8e6e60d0ce6bdeac72192c7d9b",
        filename    = filename,
        heartbeat   ="5sec"
    )
    return acl




def test_claim_ownership(acl):
    """Test that claiming ownership grants the owner role and standard perms."""
    acl.claim_ownership("Mictlantecuhtli", "MyRealm")
    
    assert acl.check("Mictlantecuhtli", "MyRealm", Acl.PERM_MANAGE) is True
    assert acl.check("Mictlantecuhtli", "MyRealm", "read") is True
    assert acl.check("Mictlantecuhtli", "MyRealm", "write") is True

def test_grant_as_owner_success(acl):
    """Test that an owner can successfully grant permissions to others."""
    # Setup
    acl.claim_ownership("Mictlantecuhtli", "MyRealm")
    
    # Action
    result = acl.grant_as_owner(
        actor       = "Mictlantecuhtli",
        target_user = "Quetzalcoatl",
        resource    = "MyRealm",
        permission  = "read"
    )
    
    # Assert
    assert result.is_ok
    assert acl.check("Quetzalcoatl", "MyRealm", "read") is True

def test_grant_as_owner_failure_unauthorized(acl):
    """Test that a non-owner CANNOT grant permissions."""
    # Setup: Mictlantecuhtli owns it. Quetzalcoatl just has read access.
    acl.claim_ownership("Mictlantecuhtli", "MyRealm")
    acl.grant_as_owner("Mictlantecuhtli", "Quetzalcoatl", "MyRealm", "read")
    
    # Action: Quetzalcoatl tries to give Xolotl write access
    result = acl.grant_as_owner(
        actor       = "Quetzalcoatl",
        target_user = "Xolotl",
        resource    = "MyRealm",
        permission  = "write"
    )
    
    # Assert
    assert result.is_err
    # Verify Xolotl did NOT get the permission
    assert acl.check("Xolotl", "MyRealm", "write") is False

def test_revoke_as_owner_success(acl):
    """Test owner can revoke permissions."""
    acl.claim_ownership("Admin", "Server")
    acl.grant_as_owner("Admin", "User", "Server", "read")
    
    assert acl.check("User", "Server", "read") is True
    
    result = acl.revoke_as_owner("Admin", "User", "Server", "read")
    
    assert result.is_ok
    assert acl.check("User", "Server", "read") is False

def test_self_revocation(acl):
    """Test that a user can always revoke their OWN permissions (leave a folder)."""
    acl.claim_ownership(actor="Admin", resource="Docs")
    acl.grant_as_owner(actor="Admin", target_user="Guest", resource="Docs", permission="read")
    
    # Guest decides to leave (revoke self)
    result = acl.revoke_as_owner(actor="Guest", target_user="Guest", resource="Docs", permission="read")
    
    assert result.is_ok
    assert acl.check("Guest", "Docs", "read") is False

def test_prevent_locking_last_owner(acl):
    """Test that the last owner cannot revoke their own ownership."""
    acl.claim_ownership(actor="TheOne", resource="Matrix")
    # Try to revoke own ownership
    result = acl.revoke_as_owner(
        actor       = "TheOne",
        target_user = "TheOne",
        resource    = "Matrix",
        permission  = Acl.PERM_MANAGE
    )
    
    assert result.is_err
    assert result.unwrap_err() == "Cannot remove the last owner. Assign a new owner first."
    # Ensure they are still owner
    assert acl.check("TheOne", "Matrix", Acl.PERM_MANAGE) is True

def test_co_ownership_workflow(acl):
    """Test that an owner can add another owner, and that new owner works."""
    # 1. Original owner
    acl.claim_ownership("Alice", "Project")
    
    # 2. Alice promotes Bob to Owner
    res = acl.grant_as_owner("Alice", "Bob", "Project", Acl.PERM_MANAGE)
    assert res.is_ok
    
    # 3. Bob (new owner) grants access to Charlie
    res_bob = acl.grant_as_owner("Bob", "Charlie", "Project", "read")
    assert res_bob.is_ok
    assert acl.check("Charlie", "Project", "read") is True
    
    # 4. Bob fires Alice (removes her ownership)
    # This should work because there are 2 owners, so Alice is not the last one.
    res_fire = acl.revoke_as_owner("Bob", "Alice", "Project", Acl.PERM_MANAGE)
    assert res_fire.is_ok
    assert acl.check("Alice", "Project", Acl.PERM_MANAGE) is False