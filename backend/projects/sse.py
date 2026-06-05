import json
from typing import Any


def encode_sse_event(event: str, data: dict[str, Any]) -> str:
    payload = {"type": event, **data}
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
