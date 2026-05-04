from __future__ import annotations

from option import Err, Ok, Result

from xoloapi.accounts.dto import AccountDTO, CreateAccountDTO
from xoloapi.accounts.models import Account
from xoloapi.errors.base import NotFoundError, XoloException


class AccountsService:
    def __init__(self, repository):
        self.repository = repository

    async def create_account(self, dto: CreateAccountDTO) -> Result[AccountDTO, XoloException]:
        account = Account(
            account_id=dto.account_id.strip(),
            name=dto.name.strip(),
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

