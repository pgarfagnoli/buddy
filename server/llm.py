"""Shared LLM helpers used by activity_loop and quests."""
from __future__ import annotations

import json
from typing import Optional


def extract_json_object(text: str) -> Optional[dict]:
    """Pull the first JSON object out of `text`, tolerating ```json fences
    and surrounding prose. Returns None if nothing parseable is found.
    """
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
