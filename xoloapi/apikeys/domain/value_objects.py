from enum import Enum


class APIKeyScope(str, Enum):
    USERS    = "users"
    ACL      = "acl"
    GROUPS   = "groups"
    RBAC     = "rbac"
    ABAC     = "abac"
    NGAC     = "ngac"
    AUDIT    = "audit"
    SCOPES   = "scopes"
    LICENSES = "licenses"
    SERVICE  = "service"
    ALL      = "all"
