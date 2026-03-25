# xoloapi/errors/__init__.py
from abc import ABC,abstractmethod
from typing import Optional,Dict,Any
from pydantic import BaseModel
from commonx.errors import * 

# ERROR_CODES = {
#     "XOLO.UNKNOWN": -1,
#     "XOLO.ERROR": 0,
#     "XOLO.USER_NOT_FOUND": 1001,
#     "XOLO.USER_ALREADY_EXISTS": 1002,
#     "XOLO.UNAUTHORIZED": 1003,
#     "XOLO.INVALID_CREDENTIALS": 1004,
#     "XOLO.TOKEN_EXPIRED": 1005,
#     "XOLO.ACCESS_DENIED": 1006,
#     "XOLO.CREATION_ERROR": 1007,
#     "XOLO.NOT_FOUND": 1008,
#     "XOLO.ALREADY_EXISTS": 1009,
#     "XOLO.SERVER_ERROR": 1010,
#     "XOLO.INVALID_LICENSE": 1011,   
# }


# class ErrorDetail(BaseModel):
#     http_status: int
#     code: Optional[str] = "XOLO.ERROR"
#     code_int: Optional[int] = 0
#     detail: str
#     raw_error: Optional[str] = None
#     metadata: Optional[Dict[str,Any]] = {}


# class XoloError(Exception,ABC):
#     def __init__(self, *args,**kwargs):
#         super().__init__(*args)
#         self.metadata = kwargs.get("metadata",{})

#     @property
#     @abstractmethod
#     def status_code(self)->int:
#         pass
#     @property
#     @abstractmethod
#     def detail(self) -> ErrorDetail:
#         """Return the details (message) of the exception."""
#         pass 
#     @property
#     @abstractmethod
#     def headers(self) -> Optional[dict]:
#         """Return optional headers for the exception."""
#         return {}

        
#     @property
#     @abstractmethod
#     def code(self) -> Optional[str]:
#         """Return an optional error code for the exception."""
#         return "XOLO.ERROR"
#     @property
#     @abstractmethod
#     def code_int(self) -> Optional[int]:
#         """Return an optional internal error code for the exception."""
#         return ERROR_CODES.get(self.code,0)
    
    
#     @abstractmethod
#     def to_http_exception(self):
#         from fastapi import HTTPException
#         return HTTPException(
#             status_code = self.status_code,
#             detail      = self.detail.model_dump(),
#             headers     = self.headers
#         )

#     def __str__(self):
#         return f"{self.detail.detail} - [{self.status_code}]: {self.code}({self.code_int})"


# class UnknownError(XoloError):
#     def __init__(self,*args,raw_detail:Optional[str]=None,headers:Optional[dict]=None):
#         super().__init__(*args)
#         self.raw_detail = raw_detail
#         self._headers   = headers

#     @property
#     def status_code(self)->int:
#         return 500

#     @property
#     def detail(self)->ErrorDetail:
#         return ErrorDetail(
#             http_status = self.status_code,
#             code        = self.code,
#             code_int    = ERROR_CODES.get(self.code, -1),
#             detail      = "Unknown error occurred",
#             raw_error   = self.raw_detail,
#             metadata    = self.metadata
#         )
    
#     @property
#     def code(self) -> Optional[str]:
#         return "XOLO.UNKNOWN"
    
#     @property
#     def code_int(self) -> Optional[int]:
#         return ERROR_CODES.get(self.code,0)
    
#     @property
#     def headers(self) -> Optional[dict]:
#         return self._headers
    
# class CreationError(XoloError):
#     def __init__(self,*args,entity:str,raw_detail:Optional[str]=None,headers:Optional[dict]=None):
#         super().__init__(*args)
#         self.raw_detail = raw_detail
#         self._headers = headers
#     @property
#     def status_code(self)->int:
#         return 409
#     @property
#     def detail(self)->ErrorDetail:
#         return ErrorDetail(
#             http_status = self.status_code,
#             code        = self.code,
#             code_int    = ERROR_CODES.get(self.code, -1),
#             detail      = f"{self.entity.upper()}: Creation failed due to a conflict or invalid state",
#             raw_error= self.raw_detail,
#             metadata    = self.metadata
#         )
#     @property
#     def code(self) -> Optional[str]:
#         return "XOLO.CREATION_ERROR"
#     @property
#     def code_int(self) -> Optional[int]:
#         return ERROR_CODES.get(self.code,0)
#     @property
#     def headers(self) -> Optional[dict]:
#         return self._headers
    

# class AccessDenied(XoloError):
#     def __init__(self,*args,raw_detail:Optional[str]=None,_headers:Optional[dict]=None):
#         super().__init__(*args)
#         self.raw_detail = raw_detail
#         self._headers = _headers
#     @property
#     def status_code(self)->int:
#         return 401
#     @property
#     def detail(self)->ErrorDetail:
#         return ErrorDetail(
#             http_status = self.status_code,
#             code        = self.code,
#             code_int    = ERROR_CODES.get(self.code, -1),
#             detail      = "Access denied: insufficient permissions to perform the requested operation",
#             raw_error   = self.raw_detail,
#             metadata    = self.metadata
#         )
#     @property
#     def code(self) -> Optional[str]:
#         return "XOLO.ACCESS_DENIED"
#     @property
#     def code_int(self) -> Optional[int]:
#         return ERROR_CODES.get(self.code,0)
#     @property
#     def headers(self) -> Optional[dict]:
#         return self._headers



# class FailedToRemoveOwner(XoloError):
#     def __init__(self, *args,raw_detail:Optional[str]=None,headers:Optional[dict]=None):
#         super().__init__(*args)
#         self.raw_detail = raw_detail
#         self._headers = headers
    
#     @property
#     def status_code(self)->int:
#         return 409
#     @property
#     def detail(self)->ErrorDetail:
#         return ErrorDetail(
#             http_status = self.status_code,
#             code        = self.code,
#             code_int    = ERROR_CODES.get(self.code, -1),
#             detail      = "Failed to remove owner: resource must have at least one owner",
#             raw_error   = self.raw_detail,
#             metadata    = self.metadata
#         )
#     @property
#     def code(self) -> Optional[str]:
#         return "XOLO.FAILED_TO_REMOVE_OWNER"
#     @property
#     def code_int(self) -> Optional[int]:
#         return ERROR_CODES.get(self.code,0)
#     @property
#     def headers(self) -> Optional[dict]:
#         return self._headers

# class FailedToClaimResource(XoloError):
#     def __init__(self,*args,raw_detail:Optional[str]=None,headers:Optional[dict]=None):
#         super().__init__(*args)
#         self.raw_detail = raw_detail
#         self._headers   = headers

#     @property
#     def status_code(self)->int:
#         return 409
    
#     @property
#     def detail(self)->ErrorDetail:
#         return ErrorDetail(
#             http_status = self.status_code,
#             code        = self.code,
#             code_int    = ERROR_CODES.get(self.code, -1),
#             detail      = "Failed to claim resource: resource is already claimed by another user",
#             raw_error   = self.raw_detail,
#             metadata    = self.metadata
#         )
#     @property
#     def code(self) -> Optional[str]:
#         return "XOLO.FAILED_TO_CLAIM_RESOURCE"
#     @property
#     def code_int(self) -> Optional[int]:
#         return ERROR_CODES.get(self.code,0)
#     @property
#     def headers(self) -> Optional[dict]:
#         return self._headers


# class TokenExpired(XoloError):
#     def __init__(self, *args,raw_detail:Optional[str]=None,headers:Optional[dict]=None):
#         super().__init__(*args)
#         self.raw_detail = raw_detail
#         self._headers = headers

#     @property
#     def detail(self)->ErrorDetail:
#         return ErrorDetail(
#             http_status = self.status_code,
#             code        = self.code,
#             code_int    = ERROR_CODES.get(self.code, -1),
#             detail      = "Token has expired",
#             raw_error   = self.raw_detail,
#             metadata    = self.metadata
#         )
#     @property
#     def code(self) -> Optional[str]:
#         return "XOLO.TOKEN_EXPIRED"
#     @property
#     def code_int(self) -> Optional[int]:
#         return ERROR_CODES.get(self.code,0)
#     @property
#     def headers(self) -> Optional[dict]:
#         return self._headers
    
#     @property
#     def status_code(self)->int:
#         return 401

# class LicenseCreationError(XoloError):
#     def __init__(self, *args,raw_detail:Optional[str]=None,headers:Optional[dict]=None):
#         super().__init__(*args)
#         self.raw_detail = raw_detail
#         self._headers   = headers
#     @property
#     def detail(self)->ErrorDetail:
#         return ErrorDetail(
#             http_status = self.status_code,
#             code        = self.code,
#             code_int    = ERROR_CODES.get(self.code, -1),
#             detail      = "License creation failed due to a conflict or invalid state",
#             raw_error   = self.raw_detail,
#             metadata    = self.metadata
#         )
#     @property
#     def code(self) -> Optional[str]:
#         return "XOLO.LICENSE_CREATION_ERROR"
#     @property
#     def code_int(self) -> Optional[int]:
#         return ERROR_CODES.get(self.code,0)
#     @property
#     def status_code(self)->int:
#         return 409
#     @property
#     def headers(self) -> Optional[dict]:
#         return self._headers



    
# class NotFound(XoloError):
#     def __init__(self,*args,entity:str,raw_detail:Optional[str]=None,headers:Optional[dict]=None):
#         super().__init__(*args)
#         self.entity     = entity
#         self.raw_detail = raw_detail
#         self._headers   = headers

#     @property
#     def detail(self)->ErrorDetail:
#         return ErrorDetail(
#             http_status = self.status_code,
#             code        = self.code,
#             code_int    = ERROR_CODES.get(self.code, -1),
#             detail      = f"{self.entity.title()} not found",
#             raw_error   = self.raw_detail,
#             metadata    = self.metadata
#         )
#     @property
#     def code(self) -> Optional[str]:
#         return "XOLO.NOT_FOUND"
#     @property
#     def code_int(self) -> Optional[int]:
#         return ERROR_CODES.get(self.code,0)
    
#     @property
#     def status_code(self)->int:
#         return 404
    
#     @property
#     def headers(self) -> Optional[dict]:
#         return self._headers

    
# class AlreadyExists(XoloError):
#     def __init__(self,entity:str,id:Optional[str] = None,*args,raw_detail:Optional[str]=None,headers:Optional[dict]=None):
#         super().__init__(*args,metadata={"entity":entity,"id":id})
#         # self.entity     = entity
#         # self.id         = id
#         self.raw_detail = raw_detail
#         self._headers   = headers

#     @property
#     def detail(self)->ErrorDetail:
#         entity = self.metadata.get("entity",'')
#         id = self.metadata.get("id",'')
#         detail = f"{entity.title()}{f'[{id}]' if id else ''} already exists"
#         return ErrorDetail(
#             http_status = self.status_code,
#             code        = self.code,
#             code_int    = ERROR_CODES.get(self.code, -1),
#             detail      = detail,
#             raw_error   = self.raw_detail,
#             metadata    = self.metadata
#         )
#     @property
#     def status_code(self)->int:
#         return 409
    
#     @property
#     def code(self) -> Optional[str]:
#         return "XOLO.ALREADY_EXISTS"
    
#     @property
#     def code_int(self) -> Optional[int]:
#         return ERROR_CODES.get(self.code,0)
    
#     @property
#     def headers(self) -> Optional[dict]:
#         return self._headers

# class Unauthorized(XoloError):
#     def __init__(self, *args,raw_detail:Optional[str]=None,headers:Optional[dict]=None):
#         super().__init__(*args)
#         self.raw_detail = raw_detail
#         self._headers   = headers
#     @property
#     def detail(self)->ErrorDetail:
#         return ErrorDetail(
#             http_status = self.status_code,
#             code        = self.code,
#             code_int    = ERROR_CODES.get(self.code, -1),
#             detail      = "Unauthorized: authentication is required and has failed or has not yet been provided",
#             raw_error   = self.raw_detail,
#             metadata    = self.metadata
#         )
#     @property
#     def code(self) -> Optional[str]:
#         return "XOLO.UNAUTHORIZED"
    
#     @property
#     def code_int(self) -> Optional[int]:
#         return ERROR_CODES.get(self.code,0)

#     @property
#     def status_code(self)->int:
#         return 401
#     @property
#     def headers(self) -> Optional[dict]:
#         return self._headers

# class UnauthorizedScope(XoloError):
#     def __init__(self, *args,raw_detail:Optional[str]=None,headers:Optional[dict]=None):
#         super().__init__(*args)
#         self.raw_detail = raw_detail
#         self._headers   = headers
#     @property
#     def detail(self)->ErrorDetail:
#         return ErrorDetail(
#             http_status = self.status_code,
#             code        = self.code,
#             code_int    = ERROR_CODES.get(self.code, -1),
#             detail      = "Unauthorized scope: the provided token does not have the required scope for this operation",
#             raw_error   = self.raw_detail,
#             metadata    = self.metadata
#         )
    
#     @property
#     def code(self) -> Optional[str]:
#         return "XOLO.UNAUTHORIZED_SCOPE"
    
#     @property
#     def code_int(self) -> Optional[int]:
#         return ERROR_CODES.get(self.code,0)

#     @property
#     def status_code(self)->int:
#         return 401
#     @property
#     def headers(self) -> Optional[dict]:
#         return self._headers
    
# class InvalidLicense(XoloError):
#     def __init__(self, *args,raw_detail:Optional[str]=None,headers:Optional[dict]=None):
#         super().__init__(*args)
#         self.raw_detail = raw_detail
#         self._headers   = headers
#     @property
#     def detail(self)->ErrorDetail:
#         return ErrorDetail(
#             http_status = self.status_code,
#             code        = self.code,
#             code_int    = ERROR_CODES.get(self.code, -1),
#             detail      = "Invalid license: the provided license is not valid or has expired",
#             raw_error   = self.raw_detail,
#             metadata    = self.metadata
#         )
    
#     @property
#     def status_code(self) -> int:
#         """HTTP status code for the invalid license."""
#         return 401  # or 403 if you prefer "Forbidden"
#     @property
#     def code(self) -> Optional[str]:
#         return "XOLO.INVALID_LICENSE"
#     @property
#     def code_int(self) -> Optional[int]:
#         return ERROR_CODES.get(self.code,0)
#     @property
#     def headers(self) -> Optional[dict]:
#         return self._headers

    
# class ServerError(XoloError):
#     def __init__(self,*args,raw_detail:Optional[str]=None,headers:Optional[dict]=None):
#         super().__init__(*args)
#         self.raw_detail = raw_detail
#         self._headers   = headers
#     @property
#     def detail(self)->ErrorDetail:
#         return ErrorDetail(
#             http_status = self.status_code,
#             code        = self.code,
#             code_int    = ERROR_CODES.get(self.code, -1),
#             detail      = "Internal server error: an unexpected error occurred on the server",
#             raw_error   = self.raw_detail,
#             metadata    = self.metadata
#         )
#     @property
#     def status_code(self)->int:
#         return 500
#     @property
#     def code(self) -> Optional[str]:
#         return "XOLO.SERVER_ERROR"
#     @property
#     def code_int(self) -> Optional[int]:
#         return ERROR_CODES.get(self.code,0)
#     @property
#     def headers(self) -> Optional[dict]:
#         return self._headers
    

# class InvalidCredentialsError(XoloError):
#     def __init__(self, *args,raw_detail:Optional[str]=None,headers:Optional[dict]=None):
#         super().__init__(*args)
#         self.raw_detail = raw_detail
#         self._headers   = headers
    
#     @property
#     def detail(self)->ErrorDetail:
#         return ErrorDetail(
#             http_status = self.status_code,
#             code        = self.code,
#             code_int    = ERROR_CODES.get(self.code, -1),
#             detail      = "Invalid credentials: the provided authentication credentials are incorrect",
#             raw_error   = self.raw_detail,
#             metadata    = self.metadata
#         )

#     @property
#     def status_code(self) -> int:
#         """HTTP status code for invalid credentials."""
#         return 401

#     @property
#     def code(self) -> Optional[str]:
#         return "XOLO.INVALID_CREDENTIALS"
#     @property
#     def code_int(self) -> Optional[int]:
#         return ERROR_CODES.get(self.code,0)
#     @property
#     def headers(self) -> Optional[dict]:
#         return self._headers
