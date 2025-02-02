from pydantic import BaseModel
class LicenseAssignedModel(BaseModel):
    username: str
    license: str
    scope: str 
    expires_at:str