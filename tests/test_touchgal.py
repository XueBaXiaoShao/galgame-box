"""TouchGal 客户端测试。"""

from __future__ import annotations

import json

import pytest

from galgame_box import http, touchgal
from galgame_box.models import Resource


@pytest.fixture
def fake_request(monkeypatch):
    async def _install(handler):
        async def fake_request(
            method, url, *, json=None, params=None, headers=None, cookies=None,
            res_type="json", handle_cf=False,
        ):
            return await handler(
                method, url, json=json, headers=headers, cookies=cookies, res_type=res_type
            )

        monkeypatch.setattr(http, "request", fake_request)

    return _install


async def test_search_uses_tag_mode_and_returns_items(fake_request) -> None:
    async def handler(method, url, **kwargs):
        assert method == "POST"
        assert url == "https://www.touchgal.ink/api/search/"
        assert "kun-patch-setting-store|state|data|kunNsfwEnable" in kwargs["cookies"]
        payload = kwargs["json"]
        assert payload["searchOption"]["searchInTag"] is True
        assert payload["searchOption"]["searchInAlias"] is False
        assert json.loads(payload["queryString"]) == [
            {"type": "keyword", "name": "恋爱"},
            {"type": "keyword", "name": "校园"},
        ]
        return {
            "galgames": [
                {
                    "id": 1,
                    "uniqueId": "u1",
                    "banner": "",
                    "name": "作品",
                    "type": [],
                    "language": [],
                    "platform": [],
                    "averageRating": 0,
                    "tags": [],
                }
            ],
            "total": 1,
        }

    await fake_request(handler)
    items, total = await touchgal.search(
        "恋爱 校园", search_in_tag=True, search_in_alias=False
    )
    assert total == 1
    assert items[0].unique_id == "u1"


async def test_random_id(fake_request) -> None:
    async def handler(method, url, **kwargs):
        assert url.endswith("/api/home/random")
        return {"uniqueId": "rnd-1"}

    await fake_request(handler)
    assert await touchgal.random_id() == "rnd-1"


async def test_resources(fake_request) -> None:
    async def handler(method, url, **kwargs):
        assert "api/patch/resource?patchId=42" in url
        return [{"id": 1, "name": "R", "links": [{"storage": "网盘"}]}]

    await fake_request(handler)
    resources = await touchgal.resources(42)
    assert isinstance(resources[0], Resource)
    assert resources[0].links[0].storage == "网盘"


def test_parse_details_extracts_title_description_previews() -> None:
    html = """
    <html><body>
      <h1 class="text-2xl font-bold leading-tight sm:text-3xl">测试作品</h1>
      <div class="kun-prose max-w-none">
        <p>第一段简介</p>
        <p>第二段简介</p>
        <div class="data-kun-img-container">
          <img src="https://img.example/1.jpg"><img src="https://img.example/2.jpg">
        </div>
      </div>
    </body></html>
    """
    details = touchgal.parse_details(html)
    assert details.title == "测试作品"
    assert "第一段简介" in details.description
    assert details.previews == [
        "https://img.example/1.jpg",
        "https://img.example/2.jpg",
    ]


def test_parse_details_missing_sections_returns_defaults() -> None:
    details = touchgal.parse_details("<html><body>empty</body></html>")
    assert details.title == ""
    assert details.previews == []
    assert details.description == ""
