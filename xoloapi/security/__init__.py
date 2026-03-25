
import os
# 
from option import Ok,Err,Result
from datetime import datetime, timedelta, timezone
from jwt import InvalidTokenError
import bcrypt
import jwt
# 
import commonx.errors as EX
class Security:
    ACCESS_TOKEN_EXPIRE_MINUTES:str =int(os.environ.get("XOLO_JWT_EXPIRE_MINUTES",15))
    SECRET_KEY:str =os.environ.get("XOLO_JWT_SECRET")
    ALGORITHM:str =os.environ.get("XOLO_JWT_ALGORITHM","HS256")
    API_KEY:str = os.environ.get("XOLO_API_KEY")
    
    @staticmethod
    async def hash_value(value: str) -> str:
        # Generate salt and hash the password
        salt            = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(value.encode('utf-8'), salt)
        return hashed_password.decode('utf-8')  # Convert bytes to string for storage

    @staticmethod
    async def verify_password(stored_value: str, provided_value: str) -> bool:
        return bcrypt.checkpw(provided_value.encode('utf-8'), stored_value.encode('utf-8'))

    @staticmethod
    def decode_access_token(token: str, secret_key: str) -> Result[dict,EX.XError]:
        try:
            payload         = jwt.decode(token, secret_key, algorithms=[Security.ALGORITHM])
            ct              = datetime.now(timezone.utc)
            current_time    = ct.timestamp()
            expiration_time = float(payload.get("exp",0))
            if current_time <= expiration_time:
                return Ok(payload)
            else:
                return Err(EX.TokenExpired(raw_detail="Token has expired."))
        except InvalidTokenError:
            return Err(EX.InvalidCredentialsError())
                            
    @staticmethod
    def create_access_token(SECRET_KEY:str,ALGORITHM:str,data: dict, expires_delta: timedelta = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt