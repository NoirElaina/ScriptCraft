from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from database import get_session
from .dependencies import CurrentSession, get_current_session
from .schemas import AuthTokenResponse, LoginRequest, RegisterRequest, UserResponse
from .service import AuthLoginResult, DuplicateUserError, InvalidCredentialsError, login_user, register_user
from .settings import AuthSettings, load_auth_settings


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    request: RegisterRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> AuthTokenResponse:
    try:
        result = register_user(session, request)
    except DuplicateUserError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _set_auth_cookie(response, result)
    return result.response


@router.post("/login", response_model=AuthTokenResponse)
def login(
    request: LoginRequest,
    response: Response,
    session: Session = Depends(get_session),
) -> AuthTokenResponse:
    try:
        result = login_user(session, request)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    _set_auth_cookie(response, result)
    return result.response


@router.get("/me", response_model=UserResponse)
def me(current_session: CurrentSession = Depends(get_current_session)) -> UserResponse:
    return UserResponse.model_validate(current_session.user, from_attributes=True)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    current_session: CurrentSession = Depends(get_current_session),
) -> Response:
    _delete_auth_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


def _set_auth_cookie(response: Response, result: AuthLoginResult) -> None:
    settings = load_auth_settings()
    response.set_cookie(
        key=settings.cookie_name,
        value=result.token,
        max_age=int(settings.token_ttl.total_seconds()),
        expires=result.response.expires_at,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )


def _delete_auth_cookie(response: Response) -> None:
    settings: AuthSettings = load_auth_settings()
    response.delete_cookie(
        key=settings.cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        path="/",
    )
