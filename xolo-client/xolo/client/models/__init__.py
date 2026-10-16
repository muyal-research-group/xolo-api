from datetime import datetime
from enum import Enum
from typing import Dict, Generic, List, Optional, Set, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

T = TypeVar("T")


class XoloDTO(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="allow")


class OperationResultDTO(XoloDTO):
    ok: bool = True


class IdResultDTO(XoloDTO):
    ok: bool = True


WILDCARD = "*"
MAX_RADIUS_KM = 5.0
MIN_RADIUS_KM = 0.1


class TimeWindowMode(str, Enum):
    WILDCARD    = "wildcard"
    DATETIME    = "datetime"
    TIME_OF_DAY = "time_of_day"
    DATE        = "date"


class GeoPointDTO(XoloDTO):
    lat: float
    lng: float


class GeoZoneDTO(XoloDTO):
    lat:       float
    lng:       float
    radius_km: float = 1.0

    @field_validator("radius_km")
    @classmethod
    def _cap_radius(cls, v: float) -> float:
        if v < MIN_RADIUS_KM or v > MAX_RADIUS_KM:
            raise ValueError(f"radius_km must be between {MIN_RADIUS_KM} and {MAX_RADIUS_KM}")
        return v


class Effect(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class MatcherVersion(str, Enum):
    LEGACY_V1 = "legacy_v1"
    GLOB_V2 = "glob_v2"


class NodeType(str, Enum):
    USER = "user"
    OBJECT = "object"
    USER_ATTRIBUTE = "user_attribute"
    OBJECT_ATTRIBUTE = "object_attribute"
    POLICY_CLASS = "policy_class"


class APIKeyScope(str, Enum):
    USERS = "users"
    ACL = "acl"
    GROUPS = "groups"
    RBAC = "rbac"
    ABAC = "abac"
    NGAC = "ngac"
    AUDIT = "audit"
    SCOPES = "scopes"
    LICENSES = "licenses"
    SERVICE = "service"
    ALL = "all"


# Request DTOs


class SignUpDTO(XoloDTO):
    username: str
    first_name: str
    last_name: str
    email: str
    password: str
    profile_photo: str = ""
    scope: str
    expiration: Optional[str] = "1h"


class CreateUserDTO(XoloDTO):
    username: str
    first_name: str
    last_name: str
    email: str
    password: str
    profile_photo: str = ""


class EnableOrDisableUserDTO(XoloDTO):
    username: str


class VerifyDTO(XoloDTO):
    access_token: str
    username: str
    secret: str


class AuthDTO(XoloDTO):
    username: str
    password: str
    scope: Optional[str] = "Xolo"
    expiration: Optional[str] = "15min"
    renew_token: Optional[bool] = False


class CreateAccountDTO(XoloDTO):
    account_id: str
    name: str
    timezone: str = "UTC"


class UpdateAccountDTO(XoloDTO):
    name: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None


class DeleteLicenseDTO(XoloDTO):
    username: str
    scope: str
    force: Optional[bool] = True


class SelfDeleteLicenseDTO(XoloDTO):
    token: str
    tmp_secret_key: str
    username: str
    scope: str
    force: Optional[bool] = True


class RotateLicenseDTO(XoloDTO):
    username:   str
    scope:      str
    expires_in: str


class AssignLicenseDTO(XoloDTO):
    username: str
    scope: str
    expires_in: str
    force: Optional[bool] = True


class PasswordRecoveryRequestDTO(XoloDTO):
    identifier: str


class PasswordRecoveryConfirmDTO(XoloDTO):
    token: str
    password: str


class CreateScopeDTO(XoloDTO):
    name: str


class AssignScopeDTO(XoloDTO):
    name: str
    username: str


class CreateGroupDTO(XoloDTO):
    name: str
    description: Optional[str] = ""
    owner_username: str


class MembersDTO(XoloDTO):
    members: List[str] = Field(default_factory=list)
    usernames: List[str] = Field(default_factory=list)


class GroupReferenceDTO(XoloDTO):
    group_id: str
    name: str
    is_active: bool


class UserReferenceDTO(XoloDTO):
    user_id: str
    username: str
    match_type: str


class GroupDTO(GroupReferenceDTO):
    description: Optional[str] = None
    owner_id: str
    owner_username: Optional[str] = None
    member_count: int = 0
    acl_usage_count: int = 0
    rbac_usage_count: int = 0
    created_at: datetime
    updated_at: datetime


class GroupPageDTO(XoloDTO):
    items: List[GroupDTO]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class GroupUsageDTO(XoloDTO):
    acl_grants: List[Dict] = Field(default_factory=list)
    rbac_assignments: List[Dict] = Field(default_factory=list)


class GrantOrRevokeDTO(XoloDTO):
    principal_id: Optional[str] = None
    principal_username: Optional[str] = None
    principal_identifier: Optional[str] = None
    principal_type: Optional[str] = None
    resource_id: str
    permissions: List[str]


class ClaimResourceDTO(XoloDTO):
    resource_id: str


class ServiceClaimResourceDTO(XoloDTO):
    resource_id: str
    owner_id: str
    owner_type: str = "USER"


class ServiceCreateGroupDTO(XoloDTO):
    name: str
    owner_id: str
    description: str = ""


class TransferResourceOwnerDTO(XoloDTO):
    principal_id: Optional[str] = None
    owner_identifier: Optional[str] = None
    principal_type: str = "USER"
    keep_previous_permissions: Optional[List[str]] = None


class TransferGroupOwnerDTO(XoloDTO):
    user_id: str
    keep_previous_as_member: bool = True


class CheckDTO(XoloDTO):
    resource_id: str
    permissions: List[str]
    principal_id:   Optional[str] = None  # if omitted → defaults to the authenticated caller
    principal_type: Optional[str] = None  # "USER" | "GROUP"



class CreateABACEventDTO(XoloDTO):
    event_id: Optional[str] = None
    subject:    str
    resource:   str
    location:   Optional[GeoZoneDTO] = None
    time_mode:  TimeWindowMode = TimeWindowMode.WILDCARD
    time_start: Optional[str] = None
    time_end:   Optional[str] = None
    action:     str


class CreateABACPolicyDTO(XoloDTO):
    name: str
    effect: Effect = Effect.ALLOW
    events: List[CreateABACEventDTO]
    timezone: Optional[str] = None


class ABACEvaluateDTO(XoloDTO):
    subject:  str
    resource: str
    location: Optional[GeoPointDTO] = None
    time:     Optional[str] = None
    action:   str


class CreateNodeDTO(XoloDTO):
    name: str
    node_type: NodeType
    properties: dict[str, str] = Field(default_factory=dict)
    user_id: Optional[str] = None
    user_identifier: Optional[str] = None
    resource_id: Optional[str] = None


class AssignDTO(XoloDTO):
    from_id: str
    to_id: str


class RemoveAssignmentDTO(XoloDTO):
    from_id: str
    to_id: str


class AssociateDTO(XoloDTO):
    user_attribute_id: str
    object_attribute_id: str
    operations: List[str]


class CheckAccessDTO(XoloDTO):
    user_id: str
    object_id: str
    operation: str


# Response DTOs mirrored from xolo-api/commonx


class CreatedUserResponseDTO(XoloDTO):
    key: str


class AccountDTO(XoloDTO):
    account_id: str
    name: Optional[str] = None
    created_at: Optional[datetime] = None
    timezone: str = "UTC"


class CreatedScopeResponseDTO(XoloDTO):
    name: str


class AssignedScopeResponseDTO(OperationResultDTO):
    name: str
    username: str


class AssignLicenseResponseDTO(OperationResultDTO):
    expires_at: str


class LicenseDTO(XoloDTO):
    username: Optional[str] = None
    scope: Optional[str] = None
    expires_at: Optional[datetime | str] = None
    issued_at: Optional[datetime | str] = None


class DeletedLicenseResponseDTO(OperationResultDTO):
    pass


class UpdateUserPasswordResponseDTO(OperationResultDTO):
    pass


class AuthenticatedDTO(XoloDTO):
    username: str
    first_name: str
    last_name: str
    email: str
    profile_photo: str
    access_token: str
    metadata: dict[str, str] = Field(default_factory=dict)
    temporal_secret: str
    user_id: Optional[str] = None


class UserDTO(XoloDTO):
    key: str
    username: str
    first_name: str
    last_name: str
    email: str
    profile_photo: str
    disabled: Optional[bool] = False


class PaginatedDTO(BaseModel, Generic[T]):
    items: List[T]
    total_count: int
    page: int
    page_size: int
    total_pages: int


class GroupDetailDTO(XoloDTO):
    id: str
    name: str
    my_role: str


class ResourceDetailDTO(XoloDTO):
    resource_id: str
    access_source: str
    permissions: Set[str] = Field(default_factory=set)


class UserResourcesDTO(XoloDTO):
    user_id: str
    groups: List[GroupDetailDTO] = Field(default_factory=list)
    owned_resources: PaginatedDTO[ResourceDetailDTO]
    shared_resources: PaginatedDTO[ResourceDetailDTO]


class EffectiveAccessDTO(XoloDTO):
    user_id: str
    resource_id: str
    is_owner: bool
    permissions: Set[str] = Field(default_factory=set)
    group_ids: List[str] = Field(default_factory=list)


class ServiceResourceDetailDTO(XoloDTO):
    resource_id: str
    permissions: Set[str] = Field(default_factory=set)
    is_owner: bool
    access_group_ids: List[str] = Field(default_factory=list)


class ServiceUserResourcesDTO(XoloDTO):
    user_id: str
    groups: List[GroupDetailDTO] = Field(default_factory=list)
    owned_resources: PaginatedDTO[ServiceResourceDetailDTO]
    shared_resources: PaginatedDTO[ServiceResourceDetailDTO]


class ResourceGrantDTO(XoloDTO):
    grant_id: str
    principal_id: str
    principal_type: str
    principal_name: Optional[str] = None
    permissions: Set[str] = Field(default_factory=set)
    is_owner: bool


class UpdateACLGrantDTO(XoloDTO):
    permissions: List[str] = Field(min_length=1)


class ResourceGrantsDTO(XoloDTO):
    resource_id: str
    grants: List[ResourceGrantDTO] = Field(default_factory=list)


class ACLPolicyPageDTO(XoloDTO):
    items: List[ResourceGrantsDTO] = Field(default_factory=list)
    total_count: int
    page: int
    page_size: int
    total_pages: int


class ACLEffectiveAccessDTO(XoloDTO):
    username: str
    user_id: str
    resource_id: str
    direct_permissions: Set[str] = Field(default_factory=set)
    group_permissions: Dict[str, Set[str]] = Field(default_factory=dict)
    ignored_disabled_groups: List[str] = Field(default_factory=list)
    is_owner: bool
    effective_permissions: Set[str] = Field(default_factory=set)
    allowed: bool
    denial_reason: Optional[str] = None


class GroupMemberDTO(XoloDTO):
    user_id: str
    username: Optional[str] = None
    joined_at: datetime


PaginatedResponseDTO = PaginatedDTO
UsersResourcesDTO = UserResourcesDTO


class ABACEventRecordDTO(XoloDTO):
    event_id:   str
    subject:    str | Dict[str, str]
    resource:   str | Dict[str, str]
    location:   Optional[Dict] = None
    time:       Optional[Dict] = None
    time_start: Optional[str | Dict[str, str]] = None
    time_end:   Optional[str | Dict[str, str]] = None
    action:     str | Dict[str, str]


class ABACPolicyDTO(XoloDTO):
    policy_id: str
    name: str
    effect: str
    events: List[ABACEventRecordDTO] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    matcher_version: MatcherVersion = MatcherVersion.LEGACY_V1
    timezone: str = "UTC"


class ABACDecisionDTO(XoloDTO):
    allowed: bool
    matched_policy: Optional[str] = None
    matched_event: Optional[str] = None
    reason: str
    matched_policy_ids: List[str] = Field(default_factory=list)
    matched_event_ids: List[str] = Field(default_factory=list)
    request_context: Dict = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)


class NGACNodeDTO(XoloDTO):
    node_id: str
    node_type: str
    name: str
    properties: dict[str, str] = Field(default_factory=dict)
    created_at: Optional[str] = None
    user_id: Optional[str] = None
    username: Optional[str] = None
    updated_at: Optional[str] = None
    resource_id: Optional[str] = None
    owner_id: str = ""


class NGACAssignmentDTO(XoloDTO):
    assignment_id: str
    from_id: str
    to_id: str
    created_at: Optional[str] = None
    owner_id: str = ""


class NGACAssociationDTO(XoloDTO):
    association_id: str
    user_attribute_id: str
    object_attribute_id: str
    operations: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    owner_id: str = ""


class NGACGraphDTO(XoloDTO):
    nodes: List[Dict] = Field(default_factory=list)
    assignments: List[Dict] = Field(default_factory=list)
    associations: List[Dict] = Field(default_factory=list)


class NGACDeletionImpactDTO(XoloDTO):
    assignments: List[Dict] = Field(default_factory=list)
    associations: List[Dict] = Field(default_factory=list)


class NGACDecisionDTO(XoloDTO):
    allowed: bool
    reason: str
    user_id: str
    object_id: str
    operation: str
    governing_policy_classes: List[Dict] = Field(default_factory=list)
    successful_paths: List[Dict] = Field(default_factory=list)
    failed_classes: List[Dict] = Field(default_factory=list)
    matching_associations: List[Dict] = Field(default_factory=list)


# Client-local response DTOs for 204 / id-only endpoints


class UserEnabledResponseDTO(OperationResultDTO):
    username: str


class DeletedAccountResponseDTO(OperationResultDTO):
    account_id: str


class DeletedUserResponseDTO(OperationResultDTO):
    username: str


class BlockedUserResponseDTO(OperationResultDTO):
    username: str


class UnblockedUserResponseDTO(OperationResultDTO):
    username: str


class UserDisabledResponseDTO(OperationResultDTO):
    username: str


class VerifyTokenResponseDTO(OperationResultDTO):
    username: str
    access_token: str


class CreatedGroupResponseDTO(IdResultDTO):
    group_id: str


class DeletedGroupResponseDTO(OperationResultDTO):
    group_id: str


class GroupMembersUpdateResponseDTO(OperationResultDTO):
    group_id: str
    members: List[str] = Field(default_factory=list)


class PermissionUpdateResponseDTO(OperationResultDTO):
    resource_id: str
    principal_id: str
    permissions: List[str] = Field(default_factory=list)
    principal_type: Optional[str] = None


class ClaimedResourceResponseDTO(OperationResultDTO):
    resource_id: str


class DeletedScopeResponseDTO(OperationResultDTO):
    name: str


class UnassignedScopeResponseDTO(OperationResultDTO):
    name: str
    username: str


class CheckPermissionResponseDTO(XoloDTO):
    has_permission: bool


class GroupMembershipResponseDTO(XoloDTO):
    user_id: str
    group_id: str
    is_member: bool


class CreatedABACPolicyResponseDTO(IdResultDTO):
    policy_id: str


class DeletedABACPolicyResponseDTO(OperationResultDTO):
    policy_id: str


class CreatedNGACNodeResponseDTO(IdResultDTO):
    node_id: str


class DeletedNGACNodeResponseDTO(OperationResultDTO):
    node_id: str


class NGACAssignmentMutationResponseDTO(OperationResultDTO):
    from_id: str
    to_id: str


class NGACAssociationMutationResponseDTO(OperationResultDTO):
    user_attribute_id: str
    object_attribute_id: str
    operations: List[str] = Field(default_factory=list)


class NGACAssociationDeletionResponseDTO(OperationResultDTO):
    association_id: str


CreateNGACNodeDTO = CreateNodeDTO
NGACAssignDTO = AssignDTO
NGACAssociateDTO = AssociateDTO
NGACCheckAccessDTO = CheckAccessDTO


class UpdateUserPasswordDTO(XoloDTO):
    username: str
    password: str


class LogoutDTO(XoloDTO):
    access_token: str
    username: str


class CreateAPIKeyDTO(XoloDTO):
    name: str
    scopes: List[APIKeyScope]
    expires_at: Optional[datetime] = None


class APIKeyMetadataDTO(XoloDTO):
    account_id: str
    key_id: str
    key_prefix: str
    name: str
    scopes: List[APIKeyScope]
    is_active: bool
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None


class CreatedAPIKeyResponseDTO(XoloDTO):
    account_id: str
    key_id: str
    key: str
    key_prefix: str
    name: str
    scopes: List[APIKeyScope]
    expires_at: Optional[datetime] = None
    created_at: datetime


class RotatedAPIKeyResponseDTO(XoloDTO):
    account_id: str
    key_id: str
    key: str
    key_prefix: str


class RevokedAPIKeyResponseDTO(OperationResultDTO):
    key_id: str


class DeletedAPIKeyResponseDTO(OperationResultDTO):
    key_id: str


class CreateRoleDTO(XoloDTO):
    name: str
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)


class UpdateRoleDTO(XoloDTO):
    name: Optional[str] = None
    description: Optional[str] = None


class PermissionDTO(XoloDTO):
    permission: str


class ParentRoleDTO(XoloDTO):
    parent_role_id: str


class AssignRoleDTO(XoloDTO):
    subject_id: Optional[str] = None
    subject_username: Optional[str] = None
    user_identifier: Optional[str] = None
    role_id: str
    subject_type: str = "user"


class UnassignRoleDTO(XoloDTO):
    subject_id: str
    role_id: str


class CheckPermissionDTO(XoloDTO):
    subject_id: Optional[str] = None
    user_identifier: Optional[str] = None
    permission: str


class RoleDTO(XoloDTO):
    role_id: str
    name: str
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    parent_role_ids: List[str] = Field(default_factory=list)


class AssignmentDTO(XoloDTO):
    assignment_id: str
    subject_id: str
    role_id: str
    subject_type: str
    subject_name: Optional[str] = None
    role_name: Optional[str] = None
    assigned_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UpdateAssignmentDTO(XoloDTO):
    subject_type: str
    role_id: str
    user_identifier: Optional[str] = None
    subject_id: Optional[str] = None


class TimezoneCatalogDTO(XoloDTO):
    default: str
    timezones: List[str]


class NotificationDTO(XoloDTO):
    notification_id: str
    category: str
    severity: str
    account_id: str
    model: str
    actor_type: str
    actor_id: str
    affected_principal: Optional[str] = None
    action: str
    target: str
    safe_detail: Dict = Field(default_factory=dict)
    link_target: Optional[str] = None
    timestamp: datetime
    expires_at: datetime
    is_read: bool = False


class NotificationPageDTO(XoloDTO):
    items: List[NotificationDTO] = Field(default_factory=list)
    next_cursor: Optional[str] = None


class CheckResultDTO(XoloDTO):
    subject_id: str
    permission: str
    has_access: bool
    matched_permission: Optional[str] = None
    resolution_paths: List[List[str]] = Field(default_factory=list)


class EffectivePermissionsDTO(XoloDTO):
    subject_id: str
    permissions: List[str] = Field(default_factory=list)
    direct_roles: List[str] = Field(default_factory=list)
    group_roles: Dict[str, List[str]] = Field(default_factory=dict)
    inherited_roles: List[str] = Field(default_factory=list)
    own_permissions: List[str] = Field(default_factory=list)
    inherited_permissions: List[str] = Field(default_factory=list)


RBACPermissionDTO = PermissionDTO
RBACCheckPermissionDTO = CheckPermissionDTO
RBACCheckResultDTO = CheckResultDTO


class HasRoleDTO(XoloDTO):
    subject_id: str
    role_id: str
    has_role: bool
    resolution_path: List[str] = Field(default_factory=list)


class AuthorizationAuditEventDTO(XoloDTO):
    event_id: str
    timestamp: datetime
    account_id: str
    model: str
    actor_type: str
    actor_id: str
    action: str
    target: str
    before: object | None = None
    after: object | None = None
    correlation_id: str


class AuthorizationAuditPageDTO(XoloDTO):
    items: List[AuthorizationAuditEventDTO]
    next_cursor: Optional[str] = None


class DeletedRoleResponseDTO(OperationResultDTO):
    role_id: str


class UnassignedRoleResponseDTO(OperationResultDTO):
    subject_id: str
    role_id: str
