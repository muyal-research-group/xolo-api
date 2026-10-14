
# --- SOLUTION ---
# Step 1: Import typing and the 'annotations' feature
from __future__ import annotations
import typing
import sys

# Step 2: Import XoloClient *only* for the type checker
from typing import Any,TypeVar
if typing.TYPE_CHECKING:
    # This import does NOT run at runtime, solving the circular import
    from xolo.client.client import XoloClient

from option import Result,Ok,Err
# --- END SOLUTION ---
# from xolo.client.client import XoloClient
T = TypeVar('T')    
class Command:
    """Base class for all Xolo-CL commands."""
    def execute(self, executor:XoloClient)->Result[T, Exception]:
        """
        Executes the command.
        The 'executor' provides context, like the client and secrets.
        """
        raise NotImplementedError
    
    def __repr__(self):
        # A simple default representation
        return f"<{self.__class__.__name__}>"


class CreateUserCommand(Command):
    def __init__(self, tokens):
        self.username = tokens.username
        # Convert parsed param groups into a simple dict
        self.params = {p['key'].lower(): p['value'] for p in tokens.params}

    def __repr__(self):
        return f"CreateUserCommand(user='{self.username}', params={self.params})"

    def execute(self, executor:XoloClient):
        print(f"[EXEC] Creating user: {self.username}")
        try:
            # Map our clean params to the client's method signature
            result = executor.create_user(
                username=self.username,
                first_name=self.params.get('firstname', ''),
                last_name=self.params.get('lastname', ''),
                email=self.params.get('email', ''),
                password=self.params.get('password', ''),
                role=self.params.get('role', self.username) # Default role = username
            )
            if result.is_ok:
                print(f"[SUCCESS] User {self.username} created.")
            else:
                print(f"[FAILURE] Could not create user {self.username}: {result.unwrap_err()}")
            
            return result
        except Exception as e:
            print(f"[ERROR] Failed to create user {self.username}: {e}", file=sys.stderr)


class UpdateUserCommand(Command):
    def __init__(self, tokens):
        self.username = tokens.username
        self.params = {p['key'].lower(): p['value'] for p in tokens.params}

    def __repr__(self):
        return f"UpdateUserCommand(user='{self.username}', params={self.params})"

    def execute(self, executor):
        # NOTE: `update_user` is not in the provided XoloClient.
        # This would call a local admin function or a different client method.
        print(f"[EXEC] Updating user: {self.username} with {self.params}")
        try:
            result = executor.update_user(
                username=self.username,
                **self.params
            )
            if result.is_ok:
                print(f"[SUCCESS] User {self.username} updated.")
            else:
                print(f"[FAILURE] Could not update user {self.username}: {result.unwrap_err()}")
            return result
        except Exception as e:
            print(f"[ERROR] Failed to update user {self.username}: {e}", file=sys.stderr)
            return Err(e)
        # print("[WARN] 'UPDATE USER' is not implemented in the provided client. Skipping.")


class DeleteUserCommand(Command):
    def __init__(self, tokens):
        self.username = tokens.username

    def __repr__(self):
        return f"DeleteUserCommand(user='{self.username}')"

    def execute(self, executor):
        # NOTE: `delete_user` is not in the provided XoloClient.
        try:
            result = executor.delete_user(
                username=self.username
            )
            if result.is_ok:
                print(f"[SUCCESS] User {self.username} deleted.")
            else:
                print(f"[FAILURE] Could not delete user {self.username}: {result.unwrap_err()}")
            return result
        except Exception as e:
            print(f"[ERROR] Failed to delete user {self.username}: {e}", file=sys.stderr)
            return Err(e)
        # print(f"[EXEC] Deleting user: {self.username}")
        # print("[WARN] 'DELETE USER' is not implemented in the provided client. Skipping.")


class CreateScopeCommand(Command):
    def __init__(self, tokens):
        self.scope_name = tokens.scope_name

    def __repr__(self):
        return f"CreateScopeCommand(scope='{self.scope_name}')"

    def execute(self, executor):
        print(f"[EXEC] Creating scope: {self.scope_name}")
        try:
            # This command requires the admin secret
            result = executor.create_scope(
                scope=self.scope_name,
                secret=executor.secret
            )
            print(f"[SUCCESS] Scope {self.scope_name} created.")
            return result
        except Exception as e:
            print(f"[ERROR] Failed to create scope {self.scope_name}: {e}", file=sys.stderr)


class AssignScopeCommand(Command):
    def __init__(self, tokens):
        self.scope_name = tokens.scope_name
        self.username = tokens.username

    def __repr__(self):
        return f"AssignScopeCommand(scope='{self.scope_name}', user='{self.username}')"

    def execute(self, executor):
        print(f"[EXEC] Assigning scope {self.scope_name} to user {self.username}")
        try:
            # This command also requires the admin secret
            result = executor.client.assign_scope(
                username=self.username,
                scope=self.scope_name,
                secret=executor.secret
            )
            print(f"[SUCCESS] Scope assigned.")
            return result
        except Exception as e:
            print(f"[ERROR] Failed to assign scope: {e}", file=sys.stderr)


class AuthenticateCommand(Command):
    def __init__(self, tokens):
        self.username = tokens.username
        self.password = tokens.password
        self.scope_name = tokens.scope_name

    def __repr__(self):
        return f"AuthenticateCommand(user='{self.username}', scope='{self.scope_name}')"

    def execute(self, executor):
        print(f"[EXEC] Authenticating user {self.username} for scope {self.scope_name}")
        try:
            result = executor.client.auth(
                username=self.username,
                password=self.password,
                scope=self.scope_name
            )
            print(f"[SUCCESS] User {self.username} authenticated.")
            return result
        except Exception as e:
            print(f"[ERROR] Failed to authenticate {self.username}: {e}", file=sys.stderr)


class CreateLicenseCommand(Command):
    def __init__(self, tokens):
        self.username = tokens.username
        self.scope_name = tokens.scope_name
        self.duration = tokens.duration

    def __repr__(self):
        return f"CreateLicenseCommand(user='{self.username}', scope='{self.scope_name}', expires='{self.duration}')"

    def execute(self, executor):
        print(f"[EXEC] Generating license for {self.username} in {self.scope_name}")
        try:
            result = executor.client.create_license(
                username=self.username,
                scope=self.scope_name,
                expires_in=self.duration,
                secret=executor.secret
            )
            print(f"[SUCCESS] License generated.")
            return result
        except Exception as e:
            print(f"[ERROR] Failed to generate license: {e}", file=sys.stderr)


class DeleteLicenseCommand(Command):
    def __init__(self, tokens):
        self.username = tokens.username
        self.scope_name = tokens.scope_name

    def __repr__(self):
        return f"DeleteLicenseCommand(user='{self.username}', scope='{self.scope_name}')"

    def execute(self, executor):
        print(f"[EXEC] Deleting license for {self.username} in {self.scope_name}")
        try:
            result = executor.client.delete_license(
                username=self.username,
                scope=self.scope_name,
                secret=executor.secret
            )
            print(f"[SUCCESS] License deleted.")
            return result
        except Exception as e:
            print(f"[ERROR] Failed to delete license: {e}", file=sys.stderr)


class GrantCommand(Command):
    def __init__(self, tokens):
        self.permission = tokens.permission
        self.resource = tokens.resource
        self.role = tokens.role

    def __repr__(self):
        return f"GrantCommand(perm='{self.permission}', res='{self.resource}', role='{self.role}')"

    def execute(self, executor):
        print(f"[EXEC] Granting '{self.permission}' on '{self.resource}' to role '{self.role}'")
        try:
            # The Xolo-CL is singular, but the client 'grants' method is plural.
            # This command class is the perfect place to do that translation.
            grants_dict = {
                self.role: {
                    self.resource: [self.permission]
                }
            }
            result = executor.client.grants(grants=grants_dict, secret=executor.secret)
            print(f"[SUCCESS] Grant executed.")
            return result
        except Exception as e:
            print(f"[ERROR] Failed to execute GRANT: {e}", file=sys.stderr)


class RevokeCommand(Command):
    def __init__(self, tokens):
        self.permission = tokens.permission
        self.resource = tokens.resource
        self.role = tokens.role

    def __repr__(self):
        return f"RevokeCommand(perm='{self.permission}', res='{self.resource}', role='{self.role}')"

    def execute(self, executor):
        # NOTE: `revoke` is not in the provided XoloClient.
        print(f"[EXEC] Revoking '{self.permission}' on '{self.resource}' from role '{self.role}'")
        print("[WARN] 'REVOKE' is not implemented in the provided client. Skipping.")


class AssignRoleCommand(Command):
    def __init__(self, tokens):
        self.role = tokens.role
        self.username = tokens.username

    def __repr__(self):
        return f"AssignRoleCommand(role='{self.role}', user='{self.username}')"

    def execute(self, executor):
        # NOTE: `assign_role` is not in the provided XoloClient.
        print(f"[EXEC] Assigning role {self.role} to user {self.username}")
        print("[WARN] 'ASSIGN ROLE' is not implemented in the provided client. Skipping.")


class LoadAbacPolicyCommand(Command):
    def __init__(self, tokens):
        self.policy_path = tokens.policy_path

    def __repr__(self):
        return f"LoadAbacPolicyCommand(path='{self.policy_path}')"

    def execute(self, executor):
        # NOTE: This is a server-side admin task, not part of the standard client.
        print(f"[EXEC] Loading ABAC policy from: {self.policy_path}")
        print("[WARN] 'LOAD ABAC POLICY' is not a client operation. Skipping.")


class EvaluateAbacRequestCommand(Command):
    def __init__(self, tokens):
        self.request_path = tokens.request_path

    def __repr__(self):
        return f"EvaluateAbacRequestCommand(path='{self.request_path}')"

    def execute(self, executor):
        # NOTE: This is a server-side admin task, not part of the standard client.
        print(f"[EXEC] Evaluating ABAC request from: {self.request_path}")
        print("[WARN] 'EVALUATE ABAC REQUEST' is not a client operation. Skipping.")


class EncryptFileCommand(Command):
    def __init__(self, tokens):
        self.input_path = tokens.input_path
        self.key = tokens.key
        self.output_path = tokens.output_path

    def __repr__(self):
        return f"EncryptFileCommand(in='{self.input_path}', out='{self.output_path}')"

    def execute(self, executor):
        # NOTE: This is a local utility, not a client-server operation.
        print(f"[EXEC] Encrypting file: {self.input_path} to {self.output_path}")
        print("[WARN] 'ENCRYPT FILE' is a local crypto operation. Skipping.")


class DecryptFileCommand(Command):
    def __init__(self, tokens):
        self.input_path = tokens.input_path
        self.key = tokens.key
        self.output_path = tokens.output_path

    def __repr__(self):
        return f"DecryptFileCommand(in='{self.input_path}', out='{self.output_path}')"

    def execute(self, executor):
        # NOTE: This is a local utility, not a client-server operation.
        print(f"[EXEC] Decrypting file: {self.input_path} to {self.output_path}")
        print("[WARN] 'DECRYPT FILE' is a local crypto operation. Skipping.")

