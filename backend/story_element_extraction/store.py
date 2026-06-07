from typing import Any


def empty_story_element_snapshot() -> dict[str, list[dict[str, Any]]]:
    return {"characters": [], "locations": [], "events": [], "scenes": []}
