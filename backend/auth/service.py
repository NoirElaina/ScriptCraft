from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from database.base import utc_now
from models.user import User
from .schemas import AuthTokenResponse, LoginRequest, RegisterRequest, UserResponse
from .security import JWTError, create_jwt_token, decode_jwt_token, hash_password, verify_password
from .settings import load_auth_settings


class AuthError(RuntimeError):
    pass


class DuplicateUserError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


@dataclass(frozen=True)
class AuthLoginResult:
    token: str
    response: AuthTokenResponse


def register_user(session: Session, request: RegisterRequest) -> AuthLoginResult:
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
    return create_auth_login_result(user)


def login_user(session: Session, request: LoginRequest) -> AuthLoginResult:
    identifier = request.identifier.strip()
    normalized_email = identifier.lower()
    user = session.scalar(
        select(User).where(or_(User.username == identifier, User.email == normalized_email)).limit(1)
    )

    if user is None or not verify_password(request.password, user.password_hash):
        raise InvalidCredentialsError("账号或密码错误")

    return create_auth_login_result(user)


def create_auth_login_result(user: User) -> AuthLoginResult:
    settings = load_auth_settings()
    expires_at = utc_now() + settings.token_ttl
    token = create_jwt_token(
        {"sub": str(user.id), "username": user.username},
        settings.jwt_secret,
        expires_at,
    )
    return AuthLoginResult(
        token=token,
        response=AuthTokenResponse(
            expires_at=expires_at,
            user=UserResponse.model_validate(user, from_attributes=True),
        ),
    )


def get_user_by_token(session: Session, token: str) -> User:
    settings = load_auth_settings()
    try:
        payload = decode_jwt_token(token, settings.jwt_secret)
    except JWTError as exc:
        raise InvalidCredentialsError(str(exc)) from exc

    user_id = _read_user_id(payload)
    user = session.get(User, user_id)
    if user is None:
        raise InvalidCredentialsError("用户不存在")
    return user


def _read_user_id(payload: dict) -> int:
    subject = payload.get("sub")
    try:
        return int(subject)
    except (TypeError, ValueError) as exc:
        raise InvalidCredentialsError("登录凭证内容无效") from exc
