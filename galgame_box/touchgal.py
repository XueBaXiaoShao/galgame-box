"""TouchGal API 客户端（搜索 / 随机 / 资源 / 页面解析）。"""

from __future__ import annotations

import json

from bs4 import BeautifulSoup

from . import http
from .config import config
from .models import Resource, TouchGalDetails, TouchGalItem

BASE_URL = "https://www.touchgal.ink/"

_HEADERS = {
    "Content-Type": "application/json",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    ),
    "referer": BASE_URL,
    "x-requested-with": "kun-fetch",
}


def _cookies() -> dict[str, str]:
    nsfw = "all" if config.nsfw == "all" else "sfw"
    cookies = {"kun-patch-setting-store|state|data|kunNsfwEnable": nsfw}
    if config.touchgal_token:
        cookies["kun-galgame-patch-moe-token"] = config.touchgal_token
    if config.cf_clearance:
        cookies["cf_clearance"] = config.cf_clearance
    return cookies


async def search(
    keyword: str,
    *,
    page: int = 1,
    limit: int = 12,
    search_in_tag: bool = False,
    search_in_alias: bool = True,
) -> tuple[list[TouchGalItem], int]:
    """搜索作品；返回（结果列表，总数）。关键词支持空格分隔的多个词。"""
    query_string = json.dumps(
        [{"type": "keyword", "name": item} for item in keyword.strip().split()]
    )
    payload = {
        "queryString": query_string,
        "limit": limit,
        "searchOption": {
            "searchInIntroduction": False,
            "searchInAlias": search_in_alias,
            "searchInTag": search_in_tag,
        },
        "page": page,
        "selectedType": "all",
        "selectedLanguage": "all",
        "selectedPlatform": "all",
        "sortField": "resource_update_time",
        "sortOrder": "desc",
        "selectedYears": ["all"],
        "selectedMonths": ["all"],
    }
    res = await http.request(
        "POST",
        BASE_URL + "api/search/",
        json=payload,
        headers=_HEADERS,
        cookies=_cookies(),
        res_type="json",
        handle_cf=True,
    )
    items = [TouchGalItem.model_validate(item) for item in res.get("galgames", [])]
    return items, int(res.get("total", 0))


async def random_id() -> str:
    """获取随机作品的 uniqueId。"""
    res = await http.request(
        "GET",
        BASE_URL + "api/home/random",
        headers=_HEADERS,
        cookies=_cookies(),
        res_type="json",
        handle_cf=True,
    )
    return str(res.get("uniqueId", ""))


async def page_html(unique_id: str) -> str:
    """获取作品详情页 HTML。"""
    return await http.request(
        "GET",
        BASE_URL + unique_id,
        headers=_HEADERS,
        cookies=_cookies(),
        res_type="text",
        handle_cf=True,
    )


async def resources(touchgal_id: int) -> list[Resource]:
    """获取作品资源（下载链接）。"""
    res = await http.request(
        "GET",
        f"{BASE_URL}api/patch/resource?patchId={touchgal_id}",
        headers=_HEADERS,
        cookies=_cookies(),
        res_type="json",
        handle_cf=True,
    )
    return [Resource.model_validate(item) for item in res]


def parse_details(html: str) -> TouchGalDetails:
    """解析作品详情页中的标题、第三方 ID、简介与预览图。"""
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    third_info: list[str] = []
    previews: list[str] = []
    description = ""

    try:
        last = soup.find("div", class_="grid gap-4 mt-6 sm:grid-cols-2")
        if last is not None:
            last = last.find_all("div")[-1]
            paths = last.find("svg").find_all("path") if last.find("svg") else []
            is_link = (
                len(paths) == 2
                and "M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"
                in (paths[0].get("d") or "")
                and "M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"
                in (paths[1].get("d") or "")
            )
            if is_link and last.find("span"):
                third_info = last.find("span").get_text().split(": ")

        h1 = soup.find("h1", class_="text-2xl font-bold leading-tight sm:text-3xl")
        if h1 and (not third_info or third_info[0] != "VNDB ID"):
            title = h1.get_text(strip=True)

        info = soup.find("div", class_="kun-prose max-w-none")
        if info is not None:
            paragraphs = info.find_all("p", recursive=False)
            description = "\n".join(p.get_text(strip=True) for p in paragraphs)
            container = info.find("div", class_="data-kun-img-container")
            if container is not None:
                previews = [
                    img.get("src") or ""
                    for img in container.find_all("img")
                    if img.get("src")
                ]
    except (AttributeError, IndexError):
        # 页面结构变化时保留已解析到的内容，不阻断主流程
        pass

    return TouchGalDetails(
        title=title,
        third_info=third_info,
        previews=previews,
        description=description,
    )
