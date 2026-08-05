"""统一管理员权限：只读取与 x_admin 共用的 admin_ids.json，不依赖环境变量。

权限组由 /shou admin add/remove（或手动编辑文件）维护；
文件不存在时视为没有任何管理员。
"""

from __future__ import annotations

import json
from pathlib import Path

from .config import config


def _file_admin_ids() -> set[int]:
    """读取共享权限文件；文件不存在或损坏返回空集合。"""
    try:
        payload = json.loads(
            (Path(config.data_dir) / "admin_ids.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return set()
    admins = payload.get("admins") if isinstance(payload, dict) else None
    if isinstance(admins, list):
        return {int(item) for item in admins if str(item).strip().isdigit()}
    return set()


def is_admin(user_id: int) -> bool:
    """管理员判断：只依据共享权限文件。"""
    return user_id in _file_admin_ids()
