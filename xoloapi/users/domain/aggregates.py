import datetime
from uuid import uuid4

import humanfriendly as HF
from pydantic import BaseModel, Field


class PasswordResetToken(BaseModel):
    request_id: str
    account_id: str
    user_id: str
    username: str
    email: str
    token_hash: str
    created_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    expires_at: datetime.datetime
    used_at: datetime.datetime | None = None

    @staticmethod
    def new(
        *,
        account_id: str,
        user_id: str,
        username: str,
        email: str,
        token_hash: str,
        expires_in: str,
    ) -> "PasswordResetToken":
        created_at = datetime.datetime.now(datetime.timezone.utc)
        expires_at = created_at + datetime.timedelta(seconds=int(HF.parse_timespan(expires_in)))
        return PasswordResetToken(
            request_id=f"prt-{uuid4().hex}",
            account_id=account_id,
            user_id=user_id,
            username=username,
            email=email,
            token_hash=token_hash,
            created_at=created_at,
            expires_at=expires_at,
        )

    def mark_used(self) -> "PasswordResetToken":
        return self.model_copy(update={"used_at": datetime.datetime.now(datetime.timezone.utc)})
