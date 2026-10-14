from enum import Enum


class PlatformRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class PlatformPermission(str, Enum):
    ACCOUNTS_READ = "accounts.read"
    ACCOUNTS_MANAGE = "accounts.manage"
    PLATFORM_USERS_READ = "platform_users.read"
    PLATFORM_USERS_MANAGE = "platform_users.manage"
    API_KEYS_READ = "api_keys.read"
    API_KEYS_MANAGE = "api_keys.manage"
    USERS_READ = "users.read"
    USERS_MANAGE = "users.manage"
    SCOPES_READ = "scopes.read"
    SCOPES_MANAGE = "scopes.manage"
    LICENSES_READ = "licenses.read"
    LICENSES_MANAGE = "licenses.manage"
    ACL_READ = "acl.read"
    ACL_MANAGE = "acl.manage"
    GROUPS_READ = "groups.read"
    GROUPS_MANAGE = "groups.manage"
    RBAC_READ = "rbac.read"
    RBAC_MANAGE = "rbac.manage"
    ABAC_READ = "abac.read"
    ABAC_MANAGE = "abac.manage"
    NGAC_READ = "ngac.read"
    NGAC_MANAGE = "ngac.manage"
    AUDIT_READ = "audit.read"

    @property
    def read_only(self) -> bool:
        return self.value.endswith(".read")
