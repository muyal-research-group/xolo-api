from typing import Dict,Set
from pydantic import BaseModel
    
class CheckDTO(BaseModel):
    role:str
    resource:str
    permission:str
    
class GrantsDTO(BaseModel):
    grants:Dict[str,Dict[str,Set]]