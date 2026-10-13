"""
Pytest unit tests for the Xolo Control Language (Xolo-CL) parser.

This file verifies that the parser defined in `xolo_cli.py` correctly
parses all valid command strings into their corresponding Command objects
and rejects invalid syntax.

To run:
1. Make sure `pytest` and `pyparsing` are installed:
   pip install pytest pyparsing
2. Save this file as `test_xolo_parser.py` in the same directory as `xolo_cli.py`.
3. Run `pytest` in your terminal.
"""

import pytest
import pyparsing as pp

# Import the components to be tested from your script
# We assume the script is named `xolo_cli.py`
from xolo.policies.parser import (
    build_parser,
    Command,
    CreateUserCommand,
    UpdateUserCommand,
    DeleteUserCommand,
    CreateScopeCommand,
    AssignScopeCommand,
    AuthenticateCommand,
    CreateLicenseCommand,
    DeleteLicenseCommand,
    GrantCommand,
    RevokeCommand,
    AssignRoleCommand,
    LoadAbacPolicyCommand,
    EvaluateAbacRequestCommand,
    EncryptFileCommand,
    DecryptFileCommand
)

@pytest.fixture(scope="module")
def parser():
    """Provides a single, reusable parser instance for all tests."""
    return build_parser()





# --- Test Cases for Each Command ---
def test_parse_create_user(parser):
    text = "CREATE USER 'testuser' WITH PASSWORD='123' EMAIL='test@test.com' ROLE='Guest'"
    result = parser.parse_string(text, parseAll=True)[0]
    
    assert isinstance(result, CreateUserCommand)
    assert result.username == 'testuser'
    assert len(result.params) == 3
    assert result.params['password'] == '123'
    assert result.params['email'] == 'test@test.com'
    assert result.params['role'] == 'Guest'

def test_parse_update_user(parser):
    text = "UPDATE USER 'testuser' SET EMAIL='new@test.com' FIRSTNAME='Test'"
    result = parser.parse_string(text, parseAll=True)[0]
    
    assert isinstance(result, UpdateUserCommand)
    assert result.username == 'testuser'
    assert len(result.params) == 2
    assert result.params['email'] == 'new@test.com'
    assert result.params['firstname'] == 'Test'

def test_parse_delete_user(parser):
    text = "DELETE USER 'testuser';" # Test with semicolon
    result = parser.parse_string(text, parseAll=True)[0]
    
    assert isinstance(result, DeleteUserCommand)
    assert result.username == 'testuser'

def test_parse_create_scope(parser):
    text = "CREATE SCOPE 'MYSCOPE'"
    result = parser.parse_string(text, parseAll=True)[0]
    
    assert isinstance(result, CreateScopeCommand)
    assert result.scope_name == 'MYSCOPE'

def test_parse_assign_scope(parser):
    text = "ASSIGN SCOPE 'MYSCOPE' TO USER 'testuser'"
    result = parser.parse_string(text, parseAll=True)[0]
    
    assert isinstance(result, AssignScopeCommand)
    assert result.scope_name == 'MYSCOPE'
    assert result.username == 'testuser'

def test_parse_authenticate(parser):
    text = "AUTHENTICATE USER 'testuser' WITH PASSWORD '123' FOR SCOPE 'MYSCOPE'"
    result = parser.parse_string(text, parseAll=True)[0]
    
    assert isinstance(result, AuthenticateCommand)
    assert result.username == 'testuser'
    assert result.password == '123'
    assert result.scope_name == 'MYSCOPE'

def test_parse_create_license(parser):
    text = "GENERATE LICENSE FOR 'testuser' IN SCOPE 'MYSCOPE' EXPIRES '30d'"
    result = parser.parse_string(text, parseAll=True)[0]
    
    assert isinstance(result, CreateLicenseCommand)
    assert result.username == 'testuser'
    assert result.scope_name == 'MYSCOPE'
    assert result.duration == '30d'

def test_parse_delete_license(parser):
    text = "DELETE LICENSE FOR 'testuser' IN SCOPE 'MYSCOPE'"
    result = parser.parse_string(text, parseAll=True)[0]
    
    assert isinstance(result, DeleteLicenseCommand)
    assert result.username == 'testuser'
    assert result.scope_name == 'MYSCOPE'

def test_parse_grant(parser):
    text = "GRANT 'read' ON 'resource-123' TO 'Admin'"
    result = parser.parse_string(text, parseAll=True)[0]
    
    assert isinstance(result, GrantCommand)
    assert result.permission == 'read'
    assert result.resource == 'resource-123'
    assert result.role == 'Admin'

def test_parse_revoke(parser):
    text = "REVOKE 'write' ON 'resource-abc' FROM 'User'"
    result = parser.parse_string(text, parseAll=True)[0]
    
    assert isinstance(result, RevokeCommand)
    assert result.permission == 'write'
    assert result.resource == 'resource-abc'
    assert result.role == 'User'

def test_parse_assign_role(parser):
    text = "ASSIGN ROLE 'Manager' TO USER 'supervisor_bob'"
    result = parser.parse_string(text, parseAll=True)[0]
    
    assert isinstance(result, AssignRoleCommand)
    assert result.role == 'Manager'
    assert result.username == 'supervisor_bob'

def test_parse_load_abac(parser):
    text = "LOAD ABAC POLICY '/path/to/my/policy.json'"
    result = parser.parse_string(text, parseAll=True)[0]
    
    assert isinstance(result, LoadAbacPolicyCommand)
    assert result.policy_path == '/path/to/my/policy.json'

def test_parse_eval_abac(parser):
    text = "EVALUATE ABAC REQUEST '/path/to/my/request.json'"
    result = parser.parse_string(text, parseAll=True)[0]
    
    assert isinstance(result, EvaluateAbacRequestCommand)
    assert result.request_path == '/path/to/my/request.json'

def test_parse_encrypt(parser):
    text = "ENCRYPT FILE '/in.txt' WITH KEY 'mykey' AS '/out.enc'"
    result = parser.parse_string(text, parseAll=True)[0]
    
    assert isinstance(result, EncryptFileCommand)
    assert result.input_path == '/in.txt'
    assert result.key == 'mykey'
    assert result.output_path == '/out.enc'

def test_parse_decrypt(parser):
    text = "DECRYPT FILE '/in.enc' WITH KEY 'mykey' AS '/out.txt'"
    result = parser.parse_string(text, parseAll=True)[0]
    
    assert isinstance(result, DecryptFileCommand)
    assert result.input_path == '/in.enc'
    assert result.key == 'mykey'
    assert result.output_path == '/out.txt'

# --- Test for invalid syntax ---

def test_parse_failure(parser):
    text = "CREATE USER 'user' WITHOUT PASSWORD" # Invalid grammar
    with pytest.raises(pp.ParseException):
        parser.parse_string(text, parseAll=True)

def test_parse_full_script(parser):
    """
    Tests the parser's ability to handle comments, newlines,
    and multiple commands.
    """
    full_script = """
    // This is a full script test
    CREATE SCOPE 'HOSPITAL1';
    # A user is created
    CREATE USER 'icastillo' WITH
        PASSWORD = 'super-secret-pass-123'
        EMAIL = 'ic@cinvestav.mx';
    
    /* Multi-line
       comment */
    GRANT 'read' ON 'RECORDS' TO 'Doctor';
    ASSIGN ROLE 'Doctor' TO USER 'icastillo';
    """
    
    results = parser.parseString(full_script, parseAll=True)
    
    assert len(results) == 4
    assert isinstance(results[0], CreateScopeCommand)
    assert isinstance(results[1], CreateUserCommand)
    assert isinstance(results[2], GrantCommand)
    assert isinstance(results[3], AssignRoleCommand)
    assert results[1].username == 'icastillo'
    assert results[2].resource == 'RECORDS'