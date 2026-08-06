"""VNDB 客户端测试（打桩 _post）。"""

from __future__ import annotations

import pytest

from galgame_box import vndb
from galgame_box.models import VNDBCharacter, VNDBProducer, VNDBVn


@pytest.fixture
def fake_post(monkeypatch):
    async def _install(handler):
        async def fake_post(path, payload):
            return await handler(path, payload)

        monkeypatch.setattr(vndb, "_post", fake_post)

    return _install


async def test_search_vn(fake_post) -> None:
    async def handler(path, payload):
        assert path == "vn"
        assert payload["filters"] == ["search", "=", "key"]
        return {"results": [{"id": "v1", "title": "Example"}]}

    await fake_post(handler)
    items = await vndb.search_vn("key", limit=5)
    assert len(items) == 1
    assert items[0].id == "v1"


async def test_get_by_id_vn(fake_post) -> None:
    async def handler(path, payload):
        assert payload["filters"] == ["id", "=", "v123"]
        return {"results": [{"id": "v123", "title": "Game"}]}

    await fake_post(handler)
    result = await vndb.get_by_id("v123")
    assert isinstance(result, VNDBVn)
    assert result.id == "v123"


async def test_get_by_id_character(fake_post) -> None:
    async def handler(path, payload):
        assert path == "character"
        return {"results": [{"id": "c9", "name": "Hero"}]}

    await fake_post(handler)
    result = await vndb.get_by_id("c9")
    assert isinstance(result, VNDBCharacter)
    assert result.name == "Hero"


async def test_get_by_id_producer_returns_vns(fake_post) -> None:
    calls = []

    async def handler(path, payload):
        calls.append(path)
        if path == "producer":
            return {"results": [{"id": "p7", "name": "Studio"}]}
        return {"results": [{"id": "v1", "title": "Game"}]}

    await fake_post(handler)
    result = await vndb.get_by_id("p7")
    assert isinstance(result, tuple)
    producer, vns = result
    assert isinstance(producer, VNDBProducer)
    assert len(vns) == 1
    assert calls == ["producer", "vn"]


async def test_get_by_id_rejects_invalid_prefix(fake_post) -> None:
    await fake_post(lambda path, payload: {})
    with pytest.raises(ValueError):
        await vndb.get_by_id("x123")


async def test_today_events_queries_both_endpoints(fake_post) -> None:
    async def handler(path, payload):
        if path == "vn":
            return {"results": [{"id": "v1", "title": "Game", "released": "2020-08-05"}]}
        return {"results": [{"id": "c1", "name": "Hero", "birthday": [8, 5]}]}

    await fake_post(handler)
    vns, characters = await vndb.today_events(8, 5, min_rating=75)
    assert len(vns) == 1
    assert characters[0].birthday == [8, 5]


async def test_find_character_builds_and_filter(fake_post) -> None:
    async def handler(path, payload):
        assert path == "character"
        assert payload["filters"][1] == ["search", "=", "Hero"]
        return {"results": []}

    await fake_post(handler)
    assert await vndb.find_character("Hero", "Game") == []


def test_waifu_filters_builds_popularity_and_year_ranges() -> None:
    assert vndb._waifu_filters() == ["and", ["sex", "=", "f"]]

    filters = vndb._waifu_filters(
        popular_threshold=5000, year_from=2000, year_to=2010
    )

    assert ["vn", "=", ["votecount", ">=", 5000]] in filters
    assert ["vn", "=", ["released", ">=", "2000-01-01"]] in filters
    assert ["vn", "=", ["released", "<=", "2010-12-31"]] in filters


def test_waifu_filters_includes_company_ids() -> None:
    filters = vndb._waifu_filters(company_ids=["p98", "p12215"])

    company_or = filters[2]
    assert company_or[0] == "or"
    assert ["vn", "=", ["developer", "=", ["id", "=", "p98"]]] in company_or[1:]
    assert ["vn", "=", ["developer", "=", ["id", "=", "p12215"]]] in company_or[1:]


async def test_resolve_company_ids_uses_search_names(monkeypatch) -> None:
    async def fake_post(path, payload):
        keyword = payload["filters"][2]
        if keyword == "Yuzusoft":
            return {"results": [{"id": "p98", "name": "Yuzusoft"}]}
        if keyword == "Yuzusoft SOUR":
            return {"results": [{"id": "p12215", "name": "Yuzusoft SOUR"}]}
        return {"results": []}

    monkeypatch.setattr(vndb, "_post", fake_post)

    ids = await vndb.resolve_company_ids(["Yuzusoft", "Yuzusoft SOUR"])

    assert ids == ["p98", "p12215"]


async def test_random_female_character_uses_fast_company_path(monkeypatch) -> None:
    calls = []

    async def fake_post(path, payload):
        calls.append((path, payload))
        if path == "vn":
            return {
                "results": [
                    {"id": "v8213", "title": "DRACU-RIOT!", "votecount": 4141}
                ]
            }
        return {
            "results": [
                {
                    "id": "c21614",
                    "name": "Oofusa Hiyori",
                    "sex": ["f"],
                    "image": {"url": "https://t.vndb.org/1.jpg"},
                    "vns": [{"id": "v8213", "title": "DRACU-RIOT!"}],
                }
            ]
        }

    monkeypatch.setattr(vndb, "_post", fake_post)

    character = await vndb.random_female_character(
        popular_threshold=5000,
        year_from=2010,
        company_ids=["p98", "p12215"],
    )

    assert character is not None
    assert character.id == "c21614"
    vn_payload = calls[0][1]
    assert ["votecount", ">=", 5000] in vn_payload["filters"][1:]
    assert ["released", ">=", "2010-01-01"] in vn_payload["filters"][1:]
    assert calls[1][0] == "character"
    assert calls[1][1]["filters"][2] == ["vn", "=", ["id", "=", "v8213"]]
