from __future__ import annotations

from option import Err, Ok, Result

from xoloapi.accounts.dto import AccountDTO, CreateAccountDTO, UpdateAccountDTO
from xoloapi.accounts.models import Account
from xoloapi.errors.base import NotFoundError, XoloException


class AccountsService:
    def __init__(self, repository):
        self.repository = repository

    async def create_account(self, dto: CreateAccountDTO) -> Result[AccountDTO, XoloException]:
        account = Account(
            account_id=dto.account_id.strip(),
            name=dto.name.strip(),
            timezone=dto.timezone,
        )
        result = await self.repository.create(account)
        if result.is_err:
            return Err(result.unwrap_err())
        created = result.unwrap()
        return Ok(AccountDTO(**created.model_dump()))

    async def list_accounts(self) -> Result[list[AccountDTO], XoloException]:
        result = await self.repository.find_all()
        if result.is_err:
            return Err(result.unwrap_err())
        return Ok([AccountDTO(**account.model_dump()) for account in result.unwrap()])

    async def get_account(self, account_id: str) -> Result[AccountDTO, XoloException]:
        result = await self.repository.find_by_id(account_id.strip())
        if result.is_err:
            return Err(result.unwrap_err())
        maybe = result.unwrap()
        if maybe.is_none:
            return Err(NotFoundError("Account", account_id.strip()))
        return Ok(AccountDTO(**maybe.unwrap().model_dump()))

    async def delete_account(self, account_id: str) -> Result[bool, XoloException]:
        return await self.repository.delete(account_id.strip())

    async def update_account(
        self, account_id: str, dto: UpdateAccountDTO
    ) -> Result[AccountDTO, XoloException]:
        current = await self.repository.find_by_id(account_id.strip())
        if current.is_err:
            return Err(current.unwrap_err())
        if current.unwrap().is_none:
            return Err(NotFoundError("Account", account_id.strip()))
        account = current.unwrap().unwrap()
        changes = dto.model_dump(exclude_unset=True)
        if "name" in changes:
            changes["name"] = changes["name"].strip()
        import datetime as dt
        changes["updated_at"] = dt.datetime.now(dt.timezone.utc)
        updated = account.model_copy(update=changes)
        result = await self.repository.update(updated)
        if result.is_err:
            return Err(result.unwrap_err())
        return Ok(AccountDTO(**result.unwrap().model_dump()))

