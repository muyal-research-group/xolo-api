from xoloapi.accounts.controller import router as accounts_router
from xoloapi.users.controller import router as users_router
from xoloapi.scopes.controller import router as scopes_router
from xoloapi.licenses.controller import router as licenses_router
from xoloapi.acl.controller import router as acl_router
from xoloapi.abac import abac_router
from xoloapi.ngac import ngac_router
from xoloapi.apikeys.controller import router as apikeys_router
from xoloapi.rbac.controller import router as rbac_router
from xoloapi.platform_users import platform_users_router
from xoloapi.groups import groups_router
from xoloapi.audit import audit_router
from xoloapi.notifications import notifications_router
