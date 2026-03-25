from fastapi import Depends,Header
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated,Type,Callable,TypeVar,Tuple,Optional
import jwt
from jwt import InvalidTokenError
import xoloapi.services as SX
import xoloapi.repositories as RX
from xoloapi.security import Security
from xoloapi.db.constants import CollectionNames
import xoloapi.db as DbX
import xoloapi.errors as EX
import xoloapi.dto as DTO
from xolo.log import Log

import xoloapi.config as Cfg

# XOLO_ACL_KEY = CX.XOLO_ACL_KEY
log            = Log(
        name                   = __name__,
        console_handler_filter = lambda x: True,
        interval               = Cfg.XOLO_LOG_INTERVAL,
        when                   = Cfg.XOLO_LOG_WHEN,
        path                   = Cfg.XOLO_LOG_PATH
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_user_service() -> SX.UsersService:
    collection             = DbX.get_collection(CollectionNames.USERS_COLLECTION_NAME)
    user_repository        = RX.UsersRepository(collection=collection)
    licenses_collection    = DbX.get_collection(CollectionNames.LICENSES_COLLECTION_NAME)
    licenses_repository    = RX.LicensesRepository(collection=licenses_collection)
    licenses_service       = SX.LicensesService(
        repository       = licenses_repository,
        users_repository = user_repository,
        secret_key=Security.SECRET_KEY
    )
    scope_collection       = DbX.get_collection(CollectionNames.SCOPES_COLLECTION_NAME)
    scope_repository       = RX.ScopesRepository(
        collection            = scope_collection,
        scope_user_collection = DbX.get_collection(CollectionNames.SCOPE_USER_COLLECTION_NAME)
    )    


    users_service          = SX.UsersService(
        repository=user_repository,
        licenses_service=licenses_service,
        scopes_repository=scope_repository
        # authentication_attempt_repository=None,
        # credentials_service = credentials_service
    )
    return users_service

async def __get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], 
    temporal_secret_key: Annotated[Optional[str], Header(alias="Temporal-Secret-Key")] = None,
    users_service: SX.UsersService = Depends(get_user_service)
):

    try:
        if temporal_secret_key is None:
            temporal_secret_key = Security.SECRET_KEY
            log.warning(
                {
                    "msg": "Temporal-Secret-Key header not provided, using default secret key."
            })

        # print("token:", token)
        # print("Temporal-Secret-Key:", temporal_secret_key)
        payload_result = Security.decode_access_token(token=token,secret_key=temporal_secret_key )
        if payload_result.is_err:
            raise EX.InvalidCredentialsError().to_http_exception()
        

        payload      = payload_result.unwrap()
        user_id: str = payload.get("sub")
        if user_id is None:
            raise EX.InvalidCredentialsError().to_http_exception()
        user_result = await users_service.get_by_id(user_id=user_id)
        if user_result.is_err:
            raise EX.InvalidCredentialsError().to_http_exception()
        user = user_result.unwrap()
        if user is None:
            raise EX.InvalidCredentialsError().to_http_exception()
        return user
    except InvalidTokenError:
        raise EX.InvalidCredentialsError().to_http_exception()




async def get_current_user(
    current_user: Annotated[DTO.UserDTO, Depends(__get_current_user)]
):
    if current_user.disabled:
        raise EX.InactiveUserError(user_id=str(current_user.user_id))
    return current_user