from enum import Enum


class NodeType(str, Enum):
    USER             = "user"
    OBJECT           = "object"
    USER_ATTRIBUTE   = "user_attribute"
    OBJECT_ATTRIBUTE = "object_attribute"
    POLICY_CLASS     = "policy_class"


# Which node types a given type can be assigned INTO (child → parent)
VALID_ASSIGNMENT_TARGETS: dict[NodeType, set[NodeType]] = {
    NodeType.USER:             {NodeType.USER_ATTRIBUTE},
    NodeType.OBJECT:           {NodeType.OBJECT_ATTRIBUTE},
    NodeType.USER_ATTRIBUTE:   {NodeType.USER_ATTRIBUTE, NodeType.POLICY_CLASS},
    NodeType.OBJECT_ATTRIBUTE: {NodeType.OBJECT_ATTRIBUTE, NodeType.POLICY_CLASS},
    NodeType.POLICY_CLASS:     set(),
}
