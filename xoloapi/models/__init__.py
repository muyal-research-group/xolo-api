#xoloapi/models/__init__.py
from pydantic import BaseModel
class LicenseAssignedModel(BaseModel):
    username: str
    license: str
    scope: str 
    expires_at:str

class User(BaseModel):
    profile_photo:str
    key:str
    first_name:str
    last_name:str
    username:str
    email:str
    hash_password:str
    role:str
# class Role