"""数据模型解析测试。"""

from __future__ import annotations

from galgame_box.models import (
    AnimeTraceResult,
    TouchGalItem,
    VNDBCharacter,
    VNDBVn,
)


def test_touchgal_item_parses_camel_case() -> None:
    item = TouchGalItem.model_validate(
        {
            "id": 42,
            "uniqueId": "abc123",
            "banner": "https://img.example/banner.jpg",
            "name": "示例作品",
            "type": ["galgame"],
            "language": ["ja"],
            "platform": ["windows"],
            "averageRating": 8.7,
            "tags": ["恋爱", "校园"],
        }
    )

    assert item.id == 42
    assert item.unique_id == "abc123"
    assert item.average_rating == 8.7
    assert item.tags == ["恋爱", "校园"]


def test_vndb_vn_parses_optional_fields() -> None:
    vn = VNDBVn.model_validate(
        {
            "id": "v123",
            "title": "Example",
            "alttitle": "示例",
            "rating": 8.1,
            "released": "2024-01-01",
            "image": {"url": "https://s.vndb.org/1.jpg"},
            "developers": [{"id": "p1", "name": "Studio"}],
            "platforms": ["win"],
        }
    )

    assert vn.id == "v123"
    assert vn.image is not None and vn.image.url == "https://s.vndb.org/1.jpg"
    assert vn.developers[0].name == "Studio"


def test_vndb_character_allows_null_image() -> None:
    character = VNDBCharacter.model_validate(
        {"id": "c1", "name": "A", "image": None, "birthday": [8, 5]}
    )
    assert character.image is None
    assert character.birthday == [8, 5]


def test_animetrace_result_parses() -> None:
    result = AnimeTraceResult.model_validate(
        {
            "code": 200,
            "ai": True,
            "data": [
                {
                    "box": [0.1, 0.2, 0.3, 0.4],
                    "not_confident": False,
                    "character": [{"work": "Example", "character": "Hero"}],
                }
            ],
        }
    )
    assert result.code == 200
    assert result.ai is True
    assert result.data[0].character[0].character == "Hero"
