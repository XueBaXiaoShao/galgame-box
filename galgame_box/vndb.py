"""VNDB Kana API 客户端。"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from . import http
from .models import VNDBCharacter, VNDBProducer, VNDBVn

KANA_URL = "https://api.vndb.org/kana/"

# 字段字符串与参考项目保持一致，覆盖查询所需全部信息
FIELDS = {
    "vn": "id,average,rating,released,length_minutes,platforms,aliases,developers{id,original,name},titles{lang,title,official},image{url},alttitle,title",
    "character": "id,name,aliases,sex,birthday,waist,hips,bust,blood_type,weight,height,cup,original,image{url},vns{id,alttitle,title}",
    "producer": "id,name,original,aliases,lang,type",
    "vn_short": "id,alttitle,title,released,rating,image{url}",
    "character_short": "id,name,original,aliases,image{url},vns{id,alttitle,title}",
    "character_event": "id,name,aliases,birthday,original,image{url}",
}


async def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    return await http.request("POST", KANA_URL + path, json=payload, res_type="json")


def _vn_list(payload: dict[str, Any]) -> list[VNDBVn]:
    return [VNDBVn.model_validate(item) for item in payload.get("results", [])]


async def search_vn(keyword: str, limit: int = 10) -> list[VNDBVn]:
    """按关键词搜索作品。"""
    payload = {
        "filters": ["search", "=", keyword],
        "fields": FIELDS["vn"],
        "results": limit,
    }
    return _vn_list(await _post("vn", payload))


async def search_character(keyword: str, limit: int = 10) -> list[VNDBCharacter]:
    """按关键词搜索角色。"""
    payload = {
        "filters": ["search", "=", keyword],
        "fields": FIELDS["character"],
        "results": limit,
    }
    return [
        VNDBCharacter.model_validate(item)
        for item in (await _post("character", payload)).get("results", [])
    ]


async def search_producer(keyword: str, limit: int = 5) -> list[VNDBProducer]:
    """按关键词搜索厂商。"""
    payload = {
        "filters": ["search", "=", keyword],
        "fields": FIELDS["producer"],
        "results": limit,
    }
    return [
        VNDBProducer.model_validate(item)
        for item in (await _post("producer", payload)).get("results", [])
    ]


async def producer_vns(producer_id: str, limit: int = 5) -> list[VNDBVn]:
    """获取厂商旗下按评分排序的代表作品。"""
    payload = {
        "filters": ["developer", "=", ["id", "=", producer_id]],
        "fields": FIELDS["vn_short"],
        "sort": "rating",
        "reverse": True,
        "results": limit,
    }
    return _vn_list(await _post("vn", payload))


async def get_by_id(
    vndb_id: str,
) -> VNDBVn | VNDBCharacter | tuple[VNDBProducer, list[VNDBVn]]:
    """通过 VNDB ID 查询：v=作品、c=角色、p=厂商。"""
    prefix = vndb_id[:1].lower()
    if prefix == "v":
        payload = {"filters": ["id", "=", vndb_id], "fields": FIELDS["vn"]}
        return _vn_list(await _post("vn", payload))[0]
    if prefix == "c":
        payload = {"filters": ["id", "=", vndb_id], "fields": FIELDS["character"]}
        items = await _post("character", payload)
        return VNDBCharacter.model_validate(items["results"][0])
    if prefix == "p":
        payload = {"filters": ["id", "=", vndb_id], "fields": FIELDS["producer"]}
        producer = VNDBProducer.model_validate(
            (await _post("producer", payload))["results"][0]
        )
        return producer, await producer_vns(producer.id)
    raise ValueError(f"无效的 VNDB ID：{vndb_id}")


async def today_events(
    month: int, day: int, min_rating: int = 75
) -> tuple[list[VNDBVn], list[VNDBCharacter]]:
    """历史上的今天：当天发售的作品（过去年份）与当天生日的角色。"""
    today = __import__("datetime").datetime.now()
    year = today.year
    released = [
        ["released", "=", f"{y}-{month:02d}-{day:02d}"]
        for y in range(1990, year)
    ]
    vn_payload = {
        "filters": ["and", ["or", *released], ["rating", ">=", min_rating]],
        "fields": FIELDS["vn_short"],
    }
    char_payload = {
        "filters": [
            "and",
            ["birthday", "=", [month, day]],
            ["vn", "=", ["rating", ">=", min_rating]],
        ],
        "fields": FIELDS["character_event"],
    }
    vn_res, char_res = await asyncio.gather(
        _post("vn", vn_payload), _post("character", char_payload)
    )
    vns = _vn_list(vn_res)
    chars = [
        VNDBCharacter.model_validate(item) for item in char_res.get("results", [])
    ]
    return vns, chars


async def find_character(character: str, work: str) -> list[VNDBCharacter]:
    """出处识别后用角色名+作品名在 VNDB 精确匹配。"""
    payload = {
        "filters": [
            "and",
            ["search", "=", character],
            ["vn", "=", ["search", "=", work]],
        ],
        "fields": FIELDS["character_short"],
        "results": 1,
    }
    return [
        VNDBCharacter.model_validate(item)
        for item in (await _post("character", payload)).get("results", [])
    ]


def _waifu_filters(
    *,
    popular_threshold: int = 0,
    year_from: int = 0,
    year_to: int = 0,
    company_ids: list[str] | None = None,
) -> list:
    """每日老婆筛选条件：女性 + 可选热度/年代/会社（VNDB 厂商 ID）。"""
    filters: list = ["and", ["sex", "=", "f"]]
    if popular_threshold and popular_threshold > 0:
        filters.append(["vn", "=", ["votecount", ">=", popular_threshold]])
    if year_from and year_from > 0:
        filters.append(["vn", "=", ["released", ">=", f"{year_from}-01-01"]])
    if year_to and year_to > 0:
        filters.append(["vn", "=", ["released", "<=", f"{year_to}-12-31"]])
    if company_ids:
        company_filters = [
            ["vn", "=", ["developer", "=", ["id", "=", producer_id]]]
            for producer_id in company_ids
        ]
        filters.append(["or", *company_filters])
    return filters


async def _character_id_bound(filters: list) -> int:
    """用当前筛选条件下最大角色 ID 估算随机页上限（ID 基本连续）。"""
    payload = {
        "filters": filters,
        "fields": "id",
        "sort": "id",
        "reverse": True,
        "results": 1,
    }
    try:
        results = (await _post("character", payload)).get("results") or []
        if results:
            return max(1, int(results[0]["id"][1:]))
    except Exception:
        pass
    return 5000


async def random_female_character(
    *,
    popular_threshold: int = 0,
    year_from: int = 0,
    year_to: int = 0,
    company_ids: list[str] | None = None,
) -> VNDBCharacter | None:
    """随机抽取一名有立绘的女性角色（每日老婆用，可带热度/年代筛选）。"""
    filters = _waifu_filters(
        popular_threshold=popular_threshold,
        year_from=year_from,
        year_to=year_to,
        company_ids=company_ids,
    )
    page_bound = await _character_id_bound(filters)
    for _ in range(8):
        page = random.randint(1, page_bound)
        payload = {
            "filters": filters,
            "fields": FIELDS["character"],
            "sort": "id",
            "results": 1,
            "page": page,
        }
        try:
            results = (await _post("character", payload)).get("results") or []
        except Exception:
            continue
        if not results:
            continue
        character = VNDBCharacter.model_validate(results[0])
        if (
            character.image
            and character.image.url
            and (character.sex or [])
            and character.sex[0] == "f"
        ):
            return character
    # 兜底：从首页前 100 名里随机挑一个
    try:
        payload = {
            "filters": filters,
            "fields": FIELDS["character"],
            "sort": "id",
            "results": 100,
        }
        results = (await _post("character", payload)).get("results") or []
        candidates = [
            VNDBCharacter.model_validate(item)
            for item in results
            if item.get("image")
            and item.get("image", {}).get("url")
            and (item.get("sex") or [])
            and item["sex"][0] == "f"
        ]
        if candidates:
            return random.choice(candidates)
    except Exception:
        pass
    return None


async def search_producer_ids(keyword: str) -> list[str]:
    """按名称搜索 VNDB 厂商 ID（精确优先，其次包含匹配）。"""
    payload = {
        "filters": ["search", "=", keyword],
        "fields": "id,name,original",
        "results": 5,
    }
    results = (await _post("producer", payload)).get("results") or []
    lower = keyword.lower()
    for item in results:
        name = (item.get("name") or "").lower()
        original = (item.get("original") or "").lower()
        if name == lower or original == lower:
            return [item["id"]]
    for item in results:
        name = (item.get("name") or "").lower()
        original = (item.get("original") or "").lower()
        if lower in name or lower in original:
            return [item["id"]]
    return []


async def resolve_company_ids(search_names: list[str]) -> list[str]:
    """把会社（含旗下品牌）的搜索名解析为去重后的 VNDB 厂商 ID 列表。"""
    ids: list[str] = []
    for name in search_names:
        for producer_id in await search_producer_ids(name):
            if producer_id not in ids:
                ids.append(producer_id)
    return ids
