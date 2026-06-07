from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from app_config import AppConfigError, load_app_config


class AuthConfigError(AppConfigError):
    pass


@dataclass(frozen=True)
class AuthSettings:
    jwt_secret: str
    cookie_name: str
    cookie_secure: bool
    cookie_samesite: str
    token_ttl: timedelta


def load_auth_settings() -> AuthSettings:
    config = load_app_config()
    auth_config = config.get("auth", {})
    if not isinstance(auth_config, dict) or not auth_config:
        raise AuthConfigError("缺少认证配置，请在 config/app.yml 中配置 auth。")

    jwt_secret = _read_text(auth_config, "jwt_secret")
    return AuthSettings(
        jwt_secret=jwt_secret,
        cookie_name=_read_text(auth_config, "cookie_name", "scriptcraft_session"),
        cookie_secure=_read_bool(auth_config, "cookie_secure", False),
        cookie_samesite=_read_text(auth_config, "cookie_samesite", "lax"),
        token_ttl=timedelta(days=_read_int(auth_config, "token_ttl_days", 30)),
    )


def _read_text(config: dict[str, Any], key: str, default: str | None = None) -> str:
    value = config.get(key, default)
    if value is None or value == "":
        raise AuthConfigError(f"config/app.yml 缺少 auth.{key}。")
    return str(value)


def _read_bool(config: dict[str, Any], key: str, default: bool) -> bool:
    value = config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _read_int(config: dict[str, Any], key: str, default: int) -> int:
    value = config.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise AuthConfigError(f"config/app.yml 中 auth.{key} 必须是整数。") from exc
