from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

from app_config import AppConfigError, load_app_config


class DatabaseConfigError(AppConfigError):
    pass


@dataclass(frozen=True)
class DatabaseSettings:
    url: str


def load_database_settings() -> DatabaseSettings:
    database_url = _load_config_database_url()

    if not database_url:
        raise DatabaseConfigError("缺少数据库配置，请在 config/app.yml 中配置 database。")

    return DatabaseSettings(url=database_url)


def _load_config_database_url() -> str:
    config = _load_app_config()
    database_config = config.get("database", {})
    if not database_config:
        return ""
    if not isinstance(database_config, dict):
        raise DatabaseConfigError("config/app.yml 中的 database 必须是对象。")

    raw_url = database_config.get("url", "")
    if raw_url:
        if not isinstance(raw_url, str):
            raise DatabaseConfigError("config/app.yml 中的 database.url 必须是字符串。")
        return raw_url

    return _build_database_url(database_config)


def _load_app_config() -> dict[str, Any]:
    try:
        return load_app_config()
    except AppConfigError as exc:
        raise DatabaseConfigError(str(exc)) from exc


def _build_database_url(database_config: dict[str, Any]) -> str:
    driver = _read_config_value(database_config, "driver", "mysql+pymysql")
    host = _read_config_value(database_config, "host")
    port = _read_config_value(database_config, "port", "3306")
    database = _read_config_value(database_config, "database")
    username = _read_config_value(database_config, "username")
    password = _read_config_value(database_config, "password")
    charset = _read_config_value(database_config, "charset", "utf8mb4")

    return (
        f"{driver}://{quote_plus(username)}:{quote_plus(password)}@"
        f"{host}:{port}/{database}?charset={quote_plus(charset)}"
    )


def _read_config_value(
    database_config: dict[str, Any],
    key: str,
    default: str | None = None,
) -> str:
    value = database_config.get(key, default)
    if value is None or value == "":
        raise DatabaseConfigError(f"config/app.yml 缺少 database.{key}。")

    return str(value)
