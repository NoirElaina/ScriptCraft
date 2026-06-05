from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_session
from models.user import User
from . import service


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentSession:
    user: User
    token: str


def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> CurrentSession:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或登录已过期")

    try:
        user = service.get_user_by_token(session, credentials.credentials)
    except service.InvalidCredentialsError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    return CurrentSession(user=user, token=credentials.credentials)


def get_current_user(current_session: CurrentSession = Depends(get_current_session)) -> User:
    return current_session.user
