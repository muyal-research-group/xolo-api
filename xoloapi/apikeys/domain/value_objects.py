from enum import Enum


class APIKeyScope(str, Enum):
    USERS    = "users"
    ACL      = "acl"
    RBAC     = "rbac"
    ABAC     = "abac"
    NGAC     = "ngac"
    POLICIES = "policies"
    SCOPES   = "scopes"
    LICENSES = "licenses"
    ALL      = "all"
