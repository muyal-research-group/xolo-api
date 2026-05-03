from fastapi import Depends,Header, Request
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated,Type,Callable,TypeVar,Tuple,Optional
import jwt
from jwt import InvalidTokenError
import xoloapi.services as SX
from xoloapi.security import Security
import xoloapi.errors as EX
import xoloapi.dto as DTO
from xolo.log import Log
from xoloapi.users.dependencies import get_users_service as get_user_service

import xoloapi.config as Cfg
from xoloapi.logging import build_log_payload

log            = Log(
        name                   = __name__,
        console_handler_filter = lambda x: True,
        interval               = Cfg.XOLO_LOG_INTERVAL,
        when                   = Cfg.XOLO_LOG_WHEN,
        path                   = Cfg.XOLO_LOG_PATH
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def __get_current_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)], 
    temporal_secret_key: Annotated[Optional[str], Header(alias="Temporal-Secret-Key")] = None,
    users_service: SX.UsersService = Depends(get_user_service)
):

    try:
        if temporal_secret_key is None:
            temporal_secret_key = Security.SECRET_KEY
            log.warning(build_log_payload("middleware.current_user.secret_key.default"))

        payload_result = Security.decode_access_token(token=token,secret_key=temporal_secret_key )
        if payload_result.is_err:
            log.warning(build_log_payload("middleware.current_user.decode.error", error=payload_result.unwrap_err()))
            raise EX.InvalidCredentialsError().to_http_exception()
        

        payload      = payload_result.unwrap()
        user_id: str = payload.get("sub")
        if user_id is None:
            log.warning(build_log_payload("middleware.current_user.missing_subject"))
            raise EX.InvalidCredentialsError().to_http_exception()
        account_id = request.path_params.get("account_id") or payload.get("aid")
        user_result = await users_service.get_by_id(user_id=user_id, account_id=account_id)
        if user_result.is_err:
            log.warning(build_log_payload("middleware.current_user.lookup.error", error=user_result.unwrap_err(), user_id=user_id))
            raise EX.InvalidCredentialsError().to_http_exception()
        user = user_result.unwrap()
        if user is None:
            log.warning(build_log_payload("middleware.current_user.lookup.empty", user_id=user_id))
            raise EX.InvalidCredentialsError().to_http_exception()
        if account_id is not None and payload.get("aid") not in (None, account_id):
            log.warning(build_log_payload("middleware.current_user.account_mismatch", user_id=user_id, token_account_id=payload.get("aid"), account_id=account_id))
            raise EX.InvalidCredentialsError().to_http_exception()
        log.debug(build_log_payload("middleware.current_user.resolve", user_id=user.key, username=user.username))
        return user
    except InvalidTokenError:
        log.warning(build_log_payload("middleware.current_user.invalid_token"))
        raise EX.InvalidCredentialsError().to_http_exception()




async def get_current_user(
    current_user: Annotated[DTO.UserDTO, Depends(__get_current_user)]
):
    if current_user.disabled:
        log.warning(build_log_payload("middleware.current_user.inactive", user_id=current_user.key, username=current_user.username))
        raise EX.InactiveUserError(user_id=str(current_user.key)).to_http_exception()
    return current_user
