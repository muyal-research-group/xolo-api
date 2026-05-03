from dotenv import load_dotenv
import os
XOLO_ENV_FILE = os.environ.get("XOLO_ENV_FILE", ".env")
if os.path.exists(XOLO_ENV_FILE):
    load_dotenv(XOLO_ENV_FILE)


def env(primary_name, default=None, *legacy_names):
    for name in (primary_name, *legacy_names):
        value = os.environ.get(name)
        if value is not None and value != "":
            return value
    return default


def str_to_bool(value): 
    return str(value).strip().lower() in ("true", "1", "yes", "on")

XOLO_LICENSE_SECRET_KEY   = env("XOLO_LICENSE_SECRET_KEY", "ed448c7a5449e9603058ce630e26c9e3befb2b15e3692411c001e0b4256852d2", "XOLO_ACL_KEY")
XOLO_ACL_KEY              = XOLO_LICENSE_SECRET_KEY
XOLO_ACL_OUTPUT_PATH      = env("XOLO_ACL_OUTPUT_PATH", "/xolo")
XOLO_ACL_FILENAME         = env("XOLO_ACL_FILENAME", "xolo-acl.enc")
XOLO_ACL_DAEMON_HEARTBEAT = env("XOLO_ACL_DAEMON_HEARTBEAT", "15min")
XOLO_LOG_NAME             = env("XOLO_LOG_NAME", "xoloapi")
XOLO_LOG_INTERVAL         = int(env("XOLO_LOG_INTERVAL", "24"))
XOLO_LOG_WHEN             = env("XOLO_LOG_WHEN", "h")
XOLO_LOG_PATH             = env("XOLO_LOG_PATH", "log")
XOLO_OPENAPI_PREFIX       = env("XOLO_OPENAPI_PREFIX", "")
XOLO_OPENAPI_TITLE        = env("XOLO_OPENAPI_TITLE", "Xolo: Identity & Accesss Management")
XOLO_OPENAPI_VERSION      = env("XOLO_OPENAPI_VERSION", "0.0.1")
XOLO_OPENAPI_SUMMARY      = env("XOLO_OPENAPI_SUMMARY", "Identity and Access Management API for Xolo Platform")
XOLO_OPENAPI_DESCRIPTION  = env("XOLO_OPENAPI_DESCRIPTION", "This API enables the management of users, roles, and permissions within the Xolo Platform.")
XOLO_OPENAPI_LOGO         = env("XOLO_OPENAPI_LOGO", "")
XOLO_CORS_ALLOW_ORIGINS   = env("XOLO_CORS_ALLOW_ORIGINS", "*").split(",")
XOLO_CORS_CREDENTIALS     = str_to_bool(env("XOLO_CORS_CREDENTIALS", "true"))
XOLO_CORS_ALLOW_METHODS   = env("XOLO_CORS_ALLOW_METHODS", "*").split(",")
XOLO_CORS_ALLOW_HEADERS   = env("XOLO_CORS_ALLOW_HEADERS", "*").split(",")
XOLO_CACHE_REDIS_HOST     = env("XOLO_CACHE_REDIS_HOST", "localhost")
XOLO_CACHE_REDIS_PORT     = int(env("XOLO_CACHE_REDIS_PORT", "6379"))
XOLO_CACHE_REDIS_URI      = env("XOLO_CACHE_REDIS_URI", f"redis://{XOLO_CACHE_REDIS_HOST}:{XOLO_CACHE_REDIS_PORT}/0")
XOLO_MONGODB_URI          = env("XOLO_MONGODB_URI", "mongodb://localhost:27018/xolo")
XOLO_MONGODB_DATABASE_NAME = env("XOLO_MONGODB_DATABASE_NAME", "xolo")
XOLO_JWT_EXPIRE_MINUTES   = int(env("XOLO_JWT_EXPIRE_MINUTES", "15"))
XOLO_JWT_SECRET           = env("XOLO_JWT_SECRET", "")
XOLO_JWT_ALGORITHM        = env("XOLO_JWT_ALGORITHM", "HS256")
XOLO_ADMIN_UI_SESSION_SECRET = env(
    "XOLO_ADMIN_UI_SESSION_SECRET",
    XOLO_JWT_SECRET or XOLO_LICENSE_SECRET_KEY,
)
XOLO_ADMIN_UI_SESSION_COOKIE_NAME = env(
    "XOLO_ADMIN_UI_SESSION_COOKIE_NAME",
    "xolo_admin_session",
)
XOLO_ADMIN_UI_SESSION_MAX_AGE = int(env("XOLO_ADMIN_UI_SESSION_MAX_AGE", "3600"))
XOLO_ADMIN_UI_SESSION_SECURE = str_to_bool(env("XOLO_ADMIN_UI_SESSION_SECURE", "false"))
XOLO_PASSWORD_RESET_TOKEN_EXPIRES_IN = env("XOLO_PASSWORD_RESET_TOKEN_EXPIRES_IN", "15min")
XOLO_PASSWORD_RESET_URL_BASE          = env("XOLO_PASSWORD_RESET_URL_BASE", "")
XOLO_PASSWORD_RESET_MAIL_SUBJECT      = env("XOLO_PASSWORD_RESET_MAIL_SUBJECT", "Xolo password reset")
XOLO_WELCOME_MAIL_SUBJECT             = env("XOLO_WELCOME_MAIL_SUBJECT", "Welcome to Xolo")
XOLO_SMTP_HOST                        = env("XOLO_SMTP_HOST", "")
XOLO_SMTP_PORT                        = int(env("XOLO_SMTP_PORT", "587"))
XOLO_SMTP_USERNAME                    = env("XOLO_SMTP_USERNAME", "")
XOLO_SMTP_PASSWORD                    = env("XOLO_SMTP_PASSWORD", "")
XOLO_SMTP_USE_TLS                     = str_to_bool(env("XOLO_SMTP_USE_TLS", "true"))
XOLO_SMTP_USE_SSL                     = str_to_bool(env("XOLO_SMTP_USE_SSL", "false"))
XOLO_MAIL_SENDER_ADDRESS              = env("XOLO_MAIL_SENDER_ADDRESS", "")
XOLO_MAIL_SENDER_NAME                 = env("XOLO_MAIL_SENDER_NAME", "Xolo")
XOLO_EMAIL_PROVIDER                   = env("XOLO_EMAIL_PROVIDER", "smtp" if XOLO_SMTP_HOST else "noop").strip().lower()
XOLO_CLOUDFLARE_ACCOUNT_ID            = env("XOLO_CLOUDFLARE_ACCOUNT_ID", "")
XOLO_CLOUDFLARE_EMAIL_API_TOKEN       = env("XOLO_CLOUDFLARE_EMAIL_API_TOKEN", "")

# Super-admin tokens — comma-separated secrets set only via environment / deployment config.
# Never exposed through any API endpoint. Requires restart to change (deliberate).
XOLO_SUPER_ADMIN_TOKENS: set[str] = {
    k.strip()
    for k in env("XOLO_SUPER_ADMIN_TOKENS", "", "XOLO_SUPER_ADMIN_KEYS").split(",")
    if k.strip()
}
XOLO_SUPER_ADMIN_KEYS = XOLO_SUPER_ADMIN_TOKENS

def is_superadmin(user) -> bool:
    return user.key in XOLO_SUPER_ADMIN_TOKENS
