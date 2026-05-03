from datetime import datetime

from pydantic import BaseModel, Field


class CreateAccountDTO(BaseModel):
    account_id: str = Field(min_length=3)
    name: str = Field(min_length=1)


class AccountDTO(BaseModel):
    account_id: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

