"""
Xolo Control Language (Xolo-CL) Interpreter and Executor

This file implements a full parser and execution framework for the Xolo-CL.
It uses `pyparsing` to convert the text-based language into a list of
Python command objects, and then provides an executor to run those commands
against a XoloClient.
"""
import pyparsing as pp
from pyparsing import (
    Word, Keyword, Literal, QuotedString, Group, Optional,
    OneOrMore, Suppress, alphas, alphanums
)
from xolo.policies.parser.models import *



def build_parser():
    # --- Basic Atoms ---
    CREATE       = Keyword("CREATE", caseless=True)
    USER         = Keyword("USER", caseless=True)
    WITH         = Keyword("WITH", caseless=True)
    PASSWORD     = Keyword("PASSWORD", caseless=True)
    EMAIL        = Keyword("EMAIL", caseless=True)
    FIRSTNAME    = Keyword("FIRSTNAME", caseless=True)
    LASTNAME     = Keyword("LASTNAME", caseless=True)
    ROLE         = Keyword("ROLE", caseless=True)
    UPDATE       = Keyword("UPDATE", caseless=True)
    SET          = Keyword("SET", caseless=True)
    DELETE       = Keyword("DELETE", caseless=True)
    AUTHENTICATE = Keyword("AUTHENTICATE", caseless=True)
    FOR          = Keyword("FOR", caseless=True)
    SCOPE        = Keyword("SCOPE", caseless=True)
    ASSIGN       = Keyword("ASSIGN", caseless=True)
    TO           = Keyword("TO", caseless=True)
    GENERATE     = Keyword("GENERATE", caseless=True)
    LICENSE      = Keyword("LICENSE", caseless=True)
    IN           = Keyword("IN", caseless=True)
    EXPIRES      = Keyword("EXPIRES", caseless=True)
    GRANT        = Keyword("GRANT", caseless=True)
    ON           = Keyword("ON", caseless=True)
    REVOKE       = Keyword("REVOKE", caseless=True)
    FROM         = Keyword("FROM", caseless=True)
    LOAD         = Keyword("LOAD", caseless=True)
    ABAC         = Keyword("ABAC", caseless=True)
    POLICY       = Keyword("POLICY", caseless=True)
    EVALUATE     = Keyword("EVALUATE", caseless=True)
    REQUEST      = Keyword("REQUEST", caseless=True)
    ENCRYPT      = Keyword("ENCRYPT", caseless=True)
    DECRYPT      = Keyword("DECRYPT", caseless=True)
    FILE         = Keyword("FILE", caseless=True)
    AS           = Keyword("AS", caseless=True)
    KEY          = Keyword("KEY", caseless=True)

    # identifier    = Word(alphas + "_", alphanums + "_-").set_name("identifier")
    quoted_string = QuotedString("'", esc_char='\\').set_name("quoted_string")
    file_path     = quoted_string.copy().set_name("file_path")
    duration      = quoted_string.copy().set_name("duration")
    
    LPAREN, RPAREN, EQ = map(Suppress, "()=")
    SEMI = Suppress(Optional(";"))
    
    # --- Command Grammars ---
    
    user_param = Group(
        (PASSWORD("key") + EQ + quoted_string("value")) |
        (EMAIL("key") + EQ + quoted_string("value")) |
        (FIRSTNAME("key") + EQ + quoted_string("value")) |
        (LASTNAME("key") + EQ + quoted_string("value")) |
        (ROLE("key") + EQ + quoted_string("value"))
    )
    
    create_user_cmd = (
        CREATE + USER + quoted_string("username") +
        WITH + OneOrMore(user_param)("params")
    ).set_parse_action(CreateUserCommand)
    
    update_user_cmd = (
        UPDATE + USER + quoted_string("username") +
        SET + OneOrMore(user_param)("params")
    ).set_parse_action(UpdateUserCommand)
    
    delete_user_cmd = (
        DELETE + USER + quoted_string("username")
    ).set_parse_action(DeleteUserCommand)
    
    auth_user_cmd = (
        AUTHENTICATE + USER + quoted_string("username") +
        WITH + PASSWORD + quoted_string("password") +
        FOR + SCOPE + quoted_string("scope_name")
    ).set_parse_action(AuthenticateCommand)
    
    create_scope_cmd = (
        CREATE + SCOPE + quoted_string("scope_name")
    ).set_parse_action(CreateScopeCommand)
    
    assign_scope_cmd = (
        ASSIGN + SCOPE + quoted_string("scope_name") +
        TO + USER + quoted_string("username")
    ).set_parse_action(AssignScopeCommand)
    
    gen_license_cmd = (
        GENERATE + LICENSE + FOR + quoted_string("username") +
        IN + SCOPE + quoted_string("scope_name") +
        EXPIRES + duration("duration")
    ).set_parse_action(CreateLicenseCommand)
    
    del_license_cmd = (
        DELETE + LICENSE + FOR + quoted_string("username") +
        IN + SCOPE + quoted_string("scope_name")
    ).set_parse_action(DeleteLicenseCommand)
    
    # *** FIX 1: ***
    # The resource name should be a quoted string, not an identifier,
    # to match the language design (e.g., 'MEDICALRECORD1').
    grant_cmd = (
        GRANT + quoted_string("permission") +
        ON + quoted_string("resource") +
        TO + quoted_string("role")
    ).set_parse_action(GrantCommand)
    
    # *** FIX 1: ***
    # Same fix for the revoke command.
    revoke_cmd = (
        REVOKE + quoted_string("permission") +
        ON + quoted_string("resource") +
        FROM + quoted_string("role")
    ).set_parse_action(RevokeCommand)
    
    assign_role_cmd = (
        ASSIGN + ROLE + quoted_string("role") +
        TO + USER + quoted_string("username")
    ).set_parse_action(AssignRoleCommand)
    
    load_abac_cmd = (
        LOAD + ABAC + POLICY + file_path("policy_path")
    ).set_parse_action(LoadAbacPolicyCommand)
    
    eval_abac_cmd = (
        EVALUATE + ABAC + REQUEST + file_path("request_path")
    ).set_parse_action(EvaluateAbacRequestCommand)
    
    encrypt_cmd = (
        ENCRYPT + FILE + file_path("input_path") +
        WITH + KEY + quoted_string("key") +
        AS + file_path("output_path")
    ).set_parse_action(EncryptFileCommand)
    
    decrypt_cmd = (
        DECRYPT + FILE + file_path("input_path") +
        WITH + KEY + quoted_string("key") +
        AS + file_path("output_path")
    ).set_parse_action(DecryptFileCommand)
    
    # --- Main Parser ---
    xolo_command = (
        create_user_cmd | update_user_cmd | delete_user_cmd |
        auth_user_cmd | create_scope_cmd | assign_scope_cmd |
        gen_license_cmd | del_license_cmd |
        grant_cmd | revoke_cmd | assign_role_cmd |
        load_abac_cmd | eval_abac_cmd |
        encrypt_cmd | decrypt_cmd
    )
    
    xolo_cl_parser = OneOrMore(xolo_command + SEMI)
    xolo_cl_parser.ignore(pp.cppStyleComment)
    xolo_cl_parser.ignore(pp.pythonStyleComment)
    
    return xolo_cl_parser

# --- 3. Executor Class ---



# --- 4. Mock Client and Test Harness ---

# class MockXoloClient:
#     """
#     A mock version of the XoloClient that prints its inputs
#     instead of making real API calls. This allows us to test the
#     parser and executor.
#     """
#     def __init__(self, hostname="mock.xolo.api", port=443):
#         print(f"[MockClient initialized at {hostname}:{port}]")
        
#     def create_user(self, username, first_name, last_name, email, password, role, **kwargs):
#         print(f"  > client.create_user(user='{username}', email='{email}', role='{role}')")
#         return {"status": "created", "username": username}

#     def auth(self, username, password, scope):
#         print(f"  > client.auth(user='{username}', scope='{scope}')")
#         return {"status": "authenticated", "token": "jwt.mock.token"}

#     def create_license(self, username, scope, expires_in, secret, **kwargs):
#         print(f"  > client.create_license(user='{username}', scope='{scope}', expires='{expires_in}', secret='{secret[:4]}...')")
#         return {"status": "license created", "license_key": "MOCK_LICENSE_KEY"}

#     def create_scope(self, scope, secret, **kwargs):
#         print(f"  > client.create_scope(scope='{scope}', secret='{secret[:4]}...')")
#         return {"status": "scope created", "name": scope}

#     def assign_scope(self, username, scope, secret, **kwargs):
#         print(f"  > client.assign_scope(user='{username}', scope='{scope}', secret='{secret[:4]}...')")
#         return {"status": "scope assigned"}

#     def grants(self, grants, secret, **kwargs):
#         print(f"  > client.grants(grants={grants}, secret='{secret[:4]}...')")
#         return {"status": "grants applied"}

#     def delete_license(self, username, scope, secret, **kwargs):
#         print(f"  > client.delete_license(user='{username}', scope='{scope}', secret='{secret[:4]}...')")
#         return {"status": "license deleted"}

# --- Main execution ---
# if __name__ == "__main__":
    
#     print("--- INITIALIZING XOLO EXECUTOR ---")
#     # 1. Initialize our mock client
#     mock_client = MockXoloClient()
    
#     # 2. Initialize the executor with the client and our admin secret
#     executor = XoloExecutor(
#         client=mock_client,
#         secret="MY_SUPER_ADMIN_SECRET_KEY_123"
#     )
#     test_scriptx=""" 
# CREATE USER alice WITH PASSWORD='alicepass' EMAIL='alice@hospital.mx';
# DELETE USER alice; 

# """
#     print("\n--- PARSING XOLO-CL SCRIPT ---")
#     # 3. Parse the script into a list of command objects
#     command_list = executor.parse_script(test_scriptx)
    
#     if command_list:
#         print(f"\nSuccessfully parsed {len(command_list)} commands.")
        
#         print("\n--- EXECUTING COMMANDS ---")
#         # 4. Execute the command list
        
#         # *** FIX 2: ***
#         # The parser returns a list of Command objects. We iterate directly over it.
#         # `command` is the object, not a group.
#         for i, command in enumerate(command_list):
#             print(f"\n--- Command {i+1}: {command} ---")
            
#             # Now we call the execute method
#             command.execute(executor)
        
#         print("\n--- EXECUTION COMPLETE ---")