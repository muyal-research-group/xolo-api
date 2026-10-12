


import jwt
import xoloapi.config as Cfg
from fastapi import Request,FastAPI, Response
# from xoloapi.server import app

def auth_cookie_middleware(app: FastAPI):
    @app.middleware("http")
    async def auth_cookie_middleware(request: Request, call_next):
        # Check if the request has a cookie named "xolo_admin_session"
        session_cookie = request.cookies.get(Cfg.XOLO_SESSION_COOKIE_NAME)
        print(f"Session cookie: {session_cookie}")  # Debugging line to check the cookie value
        if session_cookie:
            try:
                # Decode the JWT token from the cookie
                payload = jwt.decode(session_cookie, Cfg.XOLO_SESSION_COOKIE_KEY, algorithms=[Cfg.XOLO_JWT_ALGORITHM])
                # You can add additional checks here, e.g., check for expiration, roles, etc.
                request.state.user = payload  # Store user info in request state for later use
            except jwt.ExpiredSignatureError:
                # Token has expired
                request.state.user = None
            except jwt.InvalidTokenError:
                # Token is invalid
                request.state.user = None
        else:
            request.state.user = None  # No valid session

        response = await call_next(request)
        print(f"Response status code: {response.status_code}")  # Debugging line to check the response status
        return response

    @app.get("/test-auth-cookie")
    async def test_auth_cookie(request: Request):
        if request.state.user:
            # request.state.use
            return {"message": "Authenticated", "user": request.state.user}
        else:
            return {"message": "Not authenticated"}

    @app.get("/get-access")
    async def get_access(request: Request,response: Response):
        import jwt
        jwt_token = jwt.encode({"user": "test_user"}, Cfg.XOLO_SESSION_COOKIE_KEY, algorithm=Cfg.XOLO_JWT_ALGORITHM)
        response.set_cookie(
            key      = Cfg.XOLO_SESSION_COOKIE_NAME,
            value    = jwt_token,              # Replace with actual JWT token
            max_age  = Cfg.XOLO_SESSION_COOKIE_MAX_AGE,
            secure   = Cfg.XOLO_SESSION_COOKIE_SECURE,
            httponly = Cfg.XOLO_SESSION_COOKIE_HTTPONLY,
        )
        # This endpoint can be used to check if the user has access based on the session cookie
        return {"message": "Access granted"}