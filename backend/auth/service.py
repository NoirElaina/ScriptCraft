from __future__ import annotations

from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database.base import utc_now
from models.auth_session import AuthSession
from models.user import User
from .schemas import AuthTokenResponse, LoginRequest, RegisterRequest, UserResponse
from .security import create_session_token, hash_password, hash_session_token, verify_password


SESSION_TTL = timedelta(days=30)


class AuthError(RuntimeError):
    pass


class DuplicateUserError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


def register_user(session: Session, request: RegisterRequest) -> AuthTokenResponse:
    username = request.username.strip()
    email = request.email.strip().lower()

    existing_user = session.scalar(
        select(User).where(or_(User.username == username, User.email == email)).limit(1)
    )
    if existing_user is not None:
        raise DuplicateUserError("用户名或邮箱已存在")

    user = User(username=username, email=email, password_hash=hash_password(request.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return create_auth_session(session, user)


def login_user(session: Session, request: LoginRequest) -> AuthTokenResponse:
    identifier = request.identifier.strip()
    normalized_email = identifier.lower()
    user = session.scalar(
        select(User).where(or_(User.username == identifier, User.email == normalized_email)).limit(1)
    )

    if user is None or not verify_password(request.password, user.password_hash):
        raise InvalidCredentialsError("账号或密码错误")

    return create_auth_session(session, user)


def create_auth_session(session: Session, user: User) -> AuthTokenResponse:
    token = create_session_token()
    expires_at = utc_now() + SESSION_TTL
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=expires_at,
    )
    session.add(auth_session)
    session.commit()
    return AuthTokenResponse(
        token=token,
        expires_at=expires_at,
        user=UserResponse.model_validate(user, from_attributes=True),
    )


def get_user_by_token(session: Session, token: str) -> User:
    auth_session = get_session_by_token(session, token)
    user = session.get(User, auth_session.user_id)
    if user is None:
        raise InvalidCredentialsError("用户不存在")
    return user


def get_session_by_token(session: Session, token: str) -> AuthSession:
    token_hash = hash_session_token(token)
    auth_session = session.scalar(
        select(AuthSession)
        .where(
            AuthSession.token_hash == token_hash,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > utc_now(),
        )
        .limit(1)
    )
    if auth_session is None:
        raise InvalidCredentialsError("未登录或登录已过期")
    return auth_session


def revoke_session(session: Session, token: str) -> None:
    auth_session = get_session_by_token(session, token)
    auth_session.revoked_at = utc_now()
    session.commit()
