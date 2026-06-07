from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_session
from models.user import User
from . import service
from .settings import load_auth_settings


@dataclass(frozen=True)
class CurrentSession:
    user: User
    token: str


def get_current_session(
    request: Request,
    session: Session = Depends(get_session),
) -> CurrentSession:
    settings = load_auth_settings()
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或登录已过期")

    try:
        user = service.get_user_by_token(session, token)
    except service.InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return CurrentSession(user=user, token=token)


def get_current_user(current_session: CurrentSession = Depends(get_current_session)) -> User:
    return current_session.user
