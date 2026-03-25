import os

class CollectionNames: 
    USERS_COLLECTION_NAME: str = os.environ.get("XOLO_USERS_COLLECTION_NAME", "users")
    CREDENTIALS_COLLECTION_NAME: str = os.environ.get("XOLO_CREDENTIALS_COLLECTION_NAME", "credentials")
    LICENSES_COLLECTION_NAME: str = os.environ.get("XOLO_LICENSES_COLLECTION_NAME", "licenses")
    SCOPES_COLLECTION_NAME: str = os.environ.get("XOLO_SCOPES_COLLECTION_NAME", "scopes")
    SCOPE_USER_COLLECTION_NAME: str = os.environ.get("XOLO_SCOPE_USER_COLLECTION_NAME", "scope_user")
    GROUPS_COLLECTION_NAME: str = os.environ.get("XOLO_GROUPS_COLLECTION_NAME", "groups")
    GROUP_MEMBERS_COLLECTION_NAME: str = os.environ.get("XOLO_GROUP_MEMBERS_COLLECTION_NAME", "group_members")
    ACCESS_POLICIES_COLLECTION_NAME: str = os.environ.get("XOLO_ACCESS_POLICIES_COLLECTION_NAME", "access_policies")
    SECURITY_GROUPS_COLLECTION_NAME: str = os.environ.get("XOLO_SECURITY_GROUPS_COLLECTION_NAME", "security_groups")
    
