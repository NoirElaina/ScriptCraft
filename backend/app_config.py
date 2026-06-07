from pathlib import Path
from typing import Any

import yaml


class AppConfigError(RuntimeError):
    pass


def load_app_config() -> dict[str, Any]:
    config_path = Path(__file__).resolve().parents[1] / "config" / "app.yml"
    if not config_path.exists():
        return {}

    content = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if content is None:
        return {}
    if not isinstance(content, dict):
        raise AppConfigError("config/app.yml 顶层结构必须是对象。")
    return content
