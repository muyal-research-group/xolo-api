from enum import Enum
class PrincipalType(str, Enum):
    USER = "USER"
    GROUP = "GROUP"

class Permission(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    MANAGE = "sys:manage" # The "Owner" capability


