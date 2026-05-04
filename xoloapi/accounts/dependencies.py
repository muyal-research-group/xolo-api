from fastapi import Depends

from xoloapi.accounts.application.accounts_service import AccountsService
from xoloapi.accounts.infrastructure.mongo_repository import MongoAccountsRepository
from xoloapi.db import get_collection
from xoloapi.db.constants import CollectionNames


def get_accounts_service() -> AccountsService:
    return AccountsService(
        repository=MongoAccountsRepository(
            collection=get_collection(CollectionNames.ACCOUNTS_COLLECTION_NAME),
        )
    )


async def require_existing_account(
    account_id: str,
    service: AccountsService = Depends(get_accounts_service),
) -> str:
    result = await service.get_account(account_id)
    if result.is_err:
        raise result.unwrap_err().to_http_exception()
    return account_id
