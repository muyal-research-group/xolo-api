from dotenv import load_dotenv
import os
XOLO_ENV_FILE = os.environ.get("XOLO_ENV_FILE", ".env")
if os.path.exists(XOLO_ENV_FILE):
    load_dotenv(XOLO_ENV_FILE)

def str_to_bool(value): 
    return str(value).strip().lower() in ("true", "1", "yes", "on")

XOLO_ACL_KEY               = os.environ.get("XOLO_ACL_KEY","ed448c7a5449e9603058ce630e26c9e3befb2b15e3692411c001e0b4256852d2")
XOLO_ACL_OUTPUT_PATH       = os.environ.get("XOLO_ACL_OUTPUT_PATH","/xolo")
XOLO_ACL_FILENAME          = os.environ.get("XOLO_ACL_FILENAME","xolo-acl.enc")
XOLO_ACL_DAEMON_HEARTBEAT  = os.environ.get("XOLO_ACL_DAEMON_HEARTBEAT","15min")
XOLO_LOG_NAME              = os.environ.get("XOLO_LOG_NAME", "xoloapi")
XOLO_LOG_INTERVAL          = int(os.environ.get("XOLO_LOG_INTERVAL", "24"))
XOLO_LOG_WHEN              = os.environ.get("XOLO_LOG_WHEN", "h")
XOLO_LOG_PATH              = os.environ.get("XOLO_LOG_PATH", "log")
XOLO_OPENAPI_PREFIX        = os.environ.get("XOLO_OPENAPI_PREFIX","")
XOLO_OPENAPI_TITLE         = os.environ.get("XOLO_OPENAPI_TITLE","Xolo: Identity & Accesss Management")
XOLO_OPENAPI_VERSION       = os.environ.get("XOLO_OPENAPI_VERSION","0.0.1")
XOLO_OPENAPI_SUMMARY       = os.environ.get("XOLO_OPENAPI_SUMMARY","Identity and Access Management API for Xolo Platform")
XOLO_OPENAPI_DESCRIPTION   = os.environ.get("XOLO_OPENAPI_DESCRIPTION","This API enables the management of users, roles, and permissions within the Xolo Platform.")
XOLO_OPENAPI_LOGO          = os.environ.get("XOLO_OPENAPI_LOGO","")
XOLO_CORS_ALLOW_ORIGINS    = os.environ.get("XOLO_CORS_ALLOW_ORIGINS", "*").split(",")
XOLO_CORS_CREDENTIALS      = str_to_bool(os.environ.get("XOLO_CORS_CREDENTIALS", "true"))
XOLO_CORS_ALLOW_METHODS    = os.environ.get("XOLO_CORS_ALLOW_METHODS", "*").split(",")
XOLO_CORS_ALLOW_HEADERS    = os.environ.get("XOLO_CORS_ALLOW_HEADERS", "*").split(",")
XOLO_CACHE_REDIS_HOST      = os.environ.get("XOLO_CACHE_REDIS_HOST", "localhost")
XOLO_CACHE_REDIS_PORT      = int(os.environ.get("XOLO_CACHE_REDIS_PORT", "6379"))
XOLO_CACHE_REDIS_URI       = os.environ.get("XOLO_CACHE_REDIS_URI","redis://localhost:6379/0")
XOLO_MONGODB_URI           = os.environ.get("XOLO_MONGODB_URI","mongodb://localhost:27018/xolo")
XOLO_MONGODB_DATABASE_NAME = os.environ.get("XOLO_MONGODB_DATABASE_NAME","xolo")