"""每日老婆：每位用户每天一次，管理员可更换/指定。"""

from __future__ import annotations

import json
import threading
from datetime import date
from pathlib import Path
from typing import Any

from .config import config
from .models import VNDBCharacter

_lock = threading.Lock()


def _state_file() -> Path:
    return Path(config.data_dir) / "waifu_state.json"


def _load() -> dict[str, Any]:
    try:
        with _state_file().open("r", encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write(payload: dict[str, Any]) -> None:
    """写状态文件（调用方需已持有 _lock）。"""
    path = _state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _today() -> str:
    return date.today().isoformat()


def get_today_waifu(user_id: int) -> dict[str, Any] | None:
    """返回该用户今天的每日老婆；没有或已过期返回 None。"""
    payload = _load()
    record = payload.get("users", {}).get(str(user_id))
    if record and record.get("date") == _today():
        return record
    return None


def save_waifu(user_id: int, character: VNDBCharacter) -> dict[str, Any]:
    """保存（或覆盖）用户今天的每日老婆。"""
    record: dict[str, Any] = {
        "date": _today(),
        "character_id": character.id,
        "name": character.name,
        "original": character.original,
        "image_url": character.image.url if character.image else "",
        "birthday": character.birthday,
        "vns": [
            {"id": vn.id, "title": vn.alttitle or vn.title or ""}
            for vn in (character.vns or [])[:5]
        ],
    }
    with _lock:
        payload = _load()
        payload.setdefault("users", {})[str(user_id)] = record
        _write(payload)
    return record
