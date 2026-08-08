"""waifu LRU 使用记录：character_id -> 最近使用时间。"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

from .config import config

_lock = threading.Lock()


def _usage_file() -> Path:
    return Path(config.data_dir) / "waifu_usage.json"


def _load() -> dict:
    try:
        payload = json.loads(_usage_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save(payload: dict) -> None:
    path = _usage_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def usage_map() -> dict[str, str]:
    """返回 {character_id: 最近使用时间}。"""
    return _load().get("usage", {})


def mark_used(character_id: str) -> None:
    with _lock:
        payload = _load()
        payload.setdefault("usage", {})[character_id] = datetime.now().isoformat()
        _save(payload)


def last_used(character_id: str) -> str | None:
    return usage_map().get(character_id)
