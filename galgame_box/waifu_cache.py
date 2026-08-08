"""waifu 惰性缓存：把实时查询过的作品与角色保存到本地，减少重复请求。

- 实时查询后按会社回填缓存；
- 当天有新鲜缓存时直接本地随机挑选（同一筛选条件）；
- 实时查询失败时可用过期缓存兜底。
"""

from __future__ import annotations

import json
import random
import threading
from datetime import date
from pathlib import Path

from .config import config
from .models import Image, VNDBCharacter, VnRef
from . import waifu_usage

_lock = threading.Lock()


def _cache_file() -> Path:
    return Path(config.data_dir) / "waifu_cache.json"


def _load() -> dict:
    try:
        payload = json.loads(_cache_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save(payload: dict) -> None:
    path = _cache_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _entry(key: str, payload: dict) -> dict:
    return payload.setdefault("companies", {}).setdefault(
        key, {"updated": "", "vns": {}, "characters": {}}
    )


def add_company_data(
    key: str,
    vns: list[dict],
    characters: list[VNDBCharacter],
) -> None:
    """把一次实时查询的作品与角色写入缓存。"""
    with _lock:
        payload = _load()
        entry = _entry(key, payload)
        entry["updated"] = date.today().isoformat()
        for vn in vns:
            entry["vns"][vn["id"]] = {
                "id": vn["id"],
                "title": vn.get("title") or "",
                "released": vn.get("released"),
                "votecount": vn.get("votecount"),
            }
        for character in characters:
            entry["characters"][character.id] = {
                "id": character.id,
                "name": character.name,
                "original": character.original,
                "image_url": character.image.url if character.image else "",
                "sex": character.sex or [],
                "birthday": character.birthday,
                "vns": [vn.id for vn in (character.vns or [])],
            }
        _save(payload)


def is_fresh(key: str) -> bool:
    entry = _load().get("companies", {}).get(key)
    return bool(entry and entry.get("updated") == date.today().isoformat())


def has_character_for_vn(key: str, vn_id: str) -> bool:
    """该作品是否已有缓存的角色（有则刷新时跳过角色接口）。"""
    entry = _load().get("companies", {}).get(key)
    if not entry:
        return False
    characters = entry.get("characters", {})
    if not isinstance(characters, dict):
        return False
    return any(
        isinstance(character, dict) and vn_id in (character.get("vns") or [])
        for character in characters.values()
    )


def _vn_ok(
    vn: dict,
    popular_threshold: int,
    year_from: int,
    year_to: int,
) -> bool:
    if popular_threshold and popular_threshold > 0:
        votes = vn.get("votecount")
        if not isinstance(votes, int) or votes < popular_threshold:
            return False
    released = vn.get("released")
    year = int(str(released)[:4]) if isinstance(released, str) and released[:4].isdigit() else None
    if year_from and year_from > 0 and (year is None or year < year_from):
        return False
    if year_to and year_to > 0 and (year is None or year > year_to):
        return False
    return True


def pick_character(
    key: str,
    popular_threshold: int = 0,
    year_from: int = 0,
    year_to: int = 0,
    lru: bool = False,
) -> VNDBCharacter | None:
    """从缓存中按筛选条件挑角色；lru=True 时优先最久未使用的角色。"""
    entry = _load().get("companies", {}).get(key)
    if not entry:
        return None
    vns = entry.get("vns", {}) if isinstance(entry.get("vns"), dict) else {}
    characters = (
        entry.get("characters", {}) if isinstance(entry.get("characters"), dict) else {}
    )
    ok_vn_ids = {
        vn_id
        for vn_id, vn in vns.items()
        if _vn_ok(vn, popular_threshold, year_from, year_to)
    }
    candidates: list[dict] = []
    for character in characters.values():
        if not isinstance(character, dict):
            continue
        if not (character.get("sex") and character["sex"][0] == "f"):
            continue
        if not character.get("image_url"):
            continue
        if any(vn_id in ok_vn_ids for vn_id in character.get("vns", [])):
            candidates.append(character)
    if not candidates:
        return None
    if lru:
        usage = waifu_usage.usage_map()
        never_used = [candidate for candidate in candidates if candidate["id"] not in usage]
        if never_used:
            chosen = random.choice(never_used)
        else:
            oldest = min(usage[candidate["id"]] for candidate in candidates)
            bucket = [
                candidate
                for candidate in candidates
                if usage[candidate["id"]] == oldest
            ]
            chosen = random.choice(bucket)
    else:
        chosen = random.choice(candidates)
    vn_refs = [
        VnRef(
            id=vn_id,
            title=(vns.get(vn_id) or {}).get("title") or "",
        )
        for vn_id in chosen.get("vns", [])
        if vn_id in vns
    ]
    return VNDBCharacter(
        id=chosen["id"],
        name=chosen.get("name") or "",
        original=chosen.get("original"),
        birthday=chosen.get("birthday"),
        sex=chosen.get("sex") or [],
        image=Image(url=chosen["image_url"]),
        vns=vn_refs,
    )
