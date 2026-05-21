from xoloapi.db import get_collection
from xoloapi.db.constants import CollectionNames
from xoloapi.licenses.infrastructure.mongo_repository import MongoLicensesRepository


def get_licenses_repository() -> MongoLicensesRepository:
    return MongoLicensesRepository(
        collection=get_collection(CollectionNames.LICENSES_COLLECTION_NAME),
    )
