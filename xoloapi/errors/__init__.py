# xoloapi/errors/__init__.py
from abc import ABC,abstractmethod
class XoloError(Exception,ABC):

    @property
    @abstractmethod
    def status_code(self)->int:
        pass
    @property
    @abstractmethod
    def detail(self) -> str:
        """Return the details (message) of the exception."""
        pass 
    def __str__(self):
        return f"{self.detail} - [{self.status_code}]"

class TokenExpired(XoloError):
    @property
    def status_code(self)->int:
        return 401
    @property
    def detail(self)->str:
        return "Token has expired"

class LicenseCreationError(XoloError):
    @property
    def status_code(self)->int:
        return 409
    @property
    def detail(self)->str:
        return "License creation failed"


class UserNotFound(XoloError):
    @property
    def status_code(self)->int:
        return 404
    @property
    def detail(self)->str:
        return "User not found"
class NotFound(XoloError):
    def __init__(self,*args,entity:str):
        super().__init__(*args)
        self.entity = entity
    @property
    def status_code(self)->int:
        return 404
    @property
    def detail(self)->str:
        return f"{self.entity.title()} not found"

class UserAlreadyExists(XoloError):
    @property
    def status_code(self)->int:
        return 409
    @property
    def detail(self)->str:
        return "User already exists"
    
class AlreadyExists(XoloError):
    def __init__(self,entity:str,*args):
        super().__init__(*args)
        self.entity = entity

    @property
    def status_code(self)->int:
        return 409
    @property
    def detail(self)->str:
        return f"{self.entity.title()} already exists"

class Unauthorized(XoloError):
    def __init__(self, *args,message:str="credentials are invalid"):
        super().__init__(*args)
        self.message = message

    @property
    def status_code(self)->int:
        return 401
    @property
    def detail(self)->str:
        return f"Unauthorized access: {self.message}"

class UnauthorizedScope(XoloError):
    @property
    def status_code(self)->int:
        return 401
    @property
    def detail(self)->str:
        return "Unauthorized access. Please request the appropriate access permissions"
class InvalidLicense(XoloError):
    @property
    def status_code(self) -> int:
        """HTTP status code for the invalid license."""
        return 401  # or 403 if you prefer "Forbidden"

    @property
    def detail(self) -> str:
        """Message explaining that the license is invalid or missing."""
        return "Invalid license. Please verify your license credentials or contact support at jesus.castillo.b@cinvestav.mx"
    
class ServerError(XoloError):
    def __init__(self,message:str,*args):
        super().__init__(*args)
        self.message = message 
    @property
    def status_code(self)->int:
        return 500
    @property
    def detail(self)->str:
        return f"Something went wrong, please contact me at jesus.castillo.b@cinvestav.mx: {self.message}"
