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


def _settings_file() -> Path:
    return Path(config.data_dir) / "waifu_settings.json"


def default_settings() -> dict[str, Any]:
    return {"popular_threshold": 0, "year_from": 0, "year_to": 0}


def load_settings() -> dict[str, Any]:
    """读取每日老婆筛选设置；缺失或损坏时返回默认值。"""
    settings = default_settings()
    try:
        payload = json.loads(_settings_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return settings
    for key in settings:
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, int) and not isinstance(value, bool):
            settings[key] = value
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    """持久化每日老婆筛选设置。"""
    path = _settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    payload: dict[str, object] = {"version": 1}
    payload.update(settings)
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def settings_text(settings: dict[str, Any]) -> str:
    threshold = settings.get("popular_threshold", 0)
    year_from = settings.get("year_from", 0)
    year_to = settings.get("year_to", 0)
    return (
        "【每日老婆设置】\n"
        f"热度阈值：{threshold}（只抽 VNDB 投票数≥该值的作品角色；0=关闭）\n"
        f"年代范围：{year_from or '不限'} - {year_to or '不限'}\n"
        "用法：\n"
        "/shou gal waifu settings popular <N>\n"
        "/shou gal waifu settings year <起始年> [结束年]\n"
        "/shou gal waifu settings group=<群号> kaisha=<会社key|off> —— 群会社后门\n"
        "/shou gal waifu settings reset"
    )


def _group_settings_file() -> Path:
    return Path(config.data_dir) / "waifu_group_settings.json"


def _load_group_payload() -> dict[str, Any]:
    try:
        payload = json.loads(_group_settings_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def get_group_company(group_id: int) -> dict[str, Any]:
    """读取指定群的会社后门；未设置返回空。"""
    entry = _load_group_payload().get("groups", {}).get(str(group_id), {})
    companies_list = entry.get("companies") if isinstance(entry.get("companies"), list) else []
    company_ids = entry.get("company_ids") if isinstance(entry.get("company_ids"), list) else []
    return {
        "companies": [str(item) for item in companies_list],
        "company_ids": [str(item) for item in company_ids],
    }


def save_group_company(
    group_id: int, companies_list: list[str], company_ids: list[str]
) -> None:
    """保存（或清除）指定群的会社后门。"""
    path = _group_settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _load_group_payload()
    entry = payload.setdefault("groups", {}).setdefault(str(group_id), {})
    entry["companies"] = companies_list
    entry["company_ids"] = company_ids
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def get_group_year_off(group_id: int) -> bool:
    """该群是否解除了年代限制（忽略全局 year_from/year_to）。"""
    entry = _load_group_payload().get("groups", {}).get(str(group_id), {})
    return bool(entry.get("year_off"))


def save_group_year_off(group_id: int, year_off: bool) -> None:
    """设置该群是否解除年代限制。"""
    path = _group_settings_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _load_group_payload()
    entry = payload.setdefault("groups", {}).setdefault(str(group_id), {})
    entry["year_off"] = year_off
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


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


def reset_waifu(user_id: int | None) -> int:
    """重置每日老婆：user_id 为 None 时清空所有人，否则只清指定用户；返回清除数。"""
    with _lock:
        payload = _load()
        users = payload.setdefault("users", {})
        if user_id is None:
            count = len(users)
            payload["users"] = {}
        else:
            count = 1 if str(user_id) in users else 0
            users.pop(str(user_id), None)
        _write(payload)
        return count
