"""Galgame百宝盒（NoneBot 版）配置。

全部配置通过环境变量注入，前缀为 GALGAME_，与 xqq-forwarder 互不影响。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


def _env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_int_list(name: str, default: list[int] | None = None) -> list[int]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return list(default or [])
    # 兼容 "123,456" 与 JSON 数组两种写法
    if raw.startswith("["):
        try:
            return [int(i) for i in json.loads(raw)]
        except (ValueError, json.JSONDecodeError):
            return list(default or [])
    result: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            result.append(int(part))
    return result


@dataclass
class Config:
    """插件运行配置。"""

    # TouchGal 内容开关：sfw=仅全年龄，all=包含 NSFW（需要 token）
    nsfw: str = "sfw"
    # TouchGal 登录 Token（开启 NSFW 的前置条件）
    touchgal_token: str = ""
    # Cloudflare clearance Cookie（可选，建议同时安装 curl_cffi）
    cf_clearance: str = ""
    # 仅作用于本插件的代理，如 http://127.0.0.1:7897
    proxy: str = ""
    # curl_cffi 使用的 TLS 浏览器指纹
    tls: str = "chrome136"
    # 单次请求超时（秒）与重试次数
    request_timeout: int = 30
    request_retries: int = 3
    # 搜索展示条数上限
    search_limit: int = 5
    # 厂商查询时每个厂商最多展示的作品数
    producer_vns: int = 5
    # 简讯（今日事件）过滤的最低 VNDB 评分
    event_rating: int = 75
    # 简讯最多展示条数
    event_limit: int = 10
    # 角色额外信息（a血型 b身高体重 c性别 d真实性别 e三围 f罩杯）
    character_options: str = "abc"
    # 推荐一次返回数量
    recommend_count: int = 5
    # 出处识别每个检测框最多展示的候选角色数
    find_results: int = 3
    # 每日简讯推送（为空不推送）
    push_groups: list[int] = field(default_factory=list)
    push_time: str = "07:00"
    # 每日老婆：可更换老婆的管理员 QQ；未配置时回退到 SUPERUSERS
    admin_ids: list[int] = field(default_factory=list)
    # 插件数据目录（每日老婆状态等）；未配置时回退 LOCALSTORE_DATA_DIR
    data_dir: str = "data"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            nsfw=_env_str("GALGAME_NSFW", "sfw"),
            touchgal_token=_env_str("GALGAME_TOUCHGAL_TOKEN"),
            cf_clearance=_env_str("GALGAME_CF_CLEARANCE"),
            proxy=_env_str("GALGAME_PROXY"),
            tls=_env_str("GALGAME_TLS", "chrome136"),
            request_timeout=_env_int("GALGAME_REQUEST_TIMEOUT", 30),
            request_retries=_env_int("GALGAME_REQUEST_RETRIES", 3),
            search_limit=_env_int("GALGAME_SEARCH_LIMIT", 5),
            producer_vns=_env_int("GALGAME_PRODUCER_VNS", 5),
            event_rating=_env_int("GALGAME_EVENT_RATING", 75),
            event_limit=_env_int("GALGAME_EVENT_LIMIT", 10),
            character_options=_env_str("GALGAME_CHARACTER_OPTIONS", "abc"),
            recommend_count=_env_int("GALGAME_RECOMMEND_COUNT", 5),
            find_results=_env_int("GALGAME_FIND_RESULTS", 3),
            push_groups=_env_int_list("GALGAME_PUSH_GROUPS"),
            push_time=_env_str("GALGAME_PUSH_TIME", "07:00"),
            admin_ids=(
                _env_int_list("GALGAME_ADMIN_IDS")
                or _env_int_list("SUPERUSERS")
            ),
            data_dir=(
                _env_str("GALGAME_DATA_DIR")
                or _env_str("LOCALSTORE_DATA_DIR")
                or "data"
            ),
        )


config = Config.from_env()
