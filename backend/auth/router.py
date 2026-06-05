from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from database import get_session
from .dependencies import CurrentSession, get_current_session
from .schemas import AuthTokenResponse, LoginRequest, RegisterRequest, UserResponse
from .service import DuplicateUserError, InvalidCredentialsError, login_user, register_user, revoke_session


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, session: Session = Depends(get_session)) -> AuthTokenResponse:
    try:
        return register_user(session, request)
    except DuplicateUserError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/login", response_model=AuthTokenResponse)
def login(request: LoginRequest, session: Session = Depends(get_session)) -> AuthTokenResponse:
    try:
        return login_user(session, request)
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/me", response_model=UserResponse)
def me(current_session: CurrentSession = Depends(get_current_session)) -> UserResponse:
    return UserResponse.model_validate(current_session.user, from_attributes=True)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    current_session: CurrentSession = Depends(get_current_session),
    session: Session = Depends(get_session),
) -> Response:
    revoke_session(session, current_session.token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
