"""waifu 惰性缓存测试：保存查询结果，本地直接挑选。"""

from __future__ import annotations

from galgame_box import waifu_cache
from galgame_box import waifu_usage
from galgame_box.models import Image, VNDBCharacter, VnRef


def _character(
    char_id: str = "c1", title: str = "Game", vn_id: str = "v1"
) -> VNDBCharacter:
    return VNDBCharacter(
        id=char_id,
        name="Hero",
        original="ヒーロー",
        birthday=[8, 5],
        sex=["f"],
        image=Image(url="https://t.vndb.org/1.jpg"),
        vns=[VnRef(id=vn_id, title=title)],
    )


def test_add_and_pick_character(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(waifu_cache.config, "data_dir", str(tmp_path))

    waifu_cache.add_company_data(
        "yuzusoft",
        [{"id": "v1", "title": "Game", "released": "2012-01-01", "votecount": 4141}],
        [_character("c1")],
    )
    assert waifu_cache.is_fresh("yuzusoft") is True

    picked = waifu_cache.pick_character("yuzusoft")
    assert picked is not None
    assert picked.id == "c1"


def test_pick_respects_filters(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(waifu_cache.config, "data_dir", str(tmp_path))
    waifu_cache.add_company_data(
        "key",
        [
            {"id": "v1", "title": "Old", "released": "1999-01-01", "votecount": 100},
            {"id": "v2", "title": "Hot", "released": "2015-01-01", "votecount": 8000},
        ],
        [_character("c1", "Old", "v1"), _character("c2", "Hot", "v2")],
    )

    assert waifu_cache.pick_character("key", popular_threshold=5000, year_from=2016) is None
    picked = waifu_cache.pick_character("key", popular_threshold=5000, year_from=2000)
    assert picked is not None and picked.id == "c2"


def test_pick_ignores_male_or_no_image(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(waifu_cache.config, "data_dir", str(tmp_path))
    male = _character("c1")
    male.sex = ["m"]
    no_image = _character("c2")
    no_image.image = None
    waifu_cache.add_company_data(
        "smee",
        [{"id": "v1", "title": "Game", "released": None, "votecount": None}],
        [male, no_image],
    )

    assert waifu_cache.pick_character("smee") is None


def test_pick_character_lru_prefers_least_used(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(waifu_cache.config, "data_dir", str(tmp_path))
    monkeypatch.setattr(waifu_usage.config, "data_dir", str(tmp_path))
    waifu_cache.add_company_data(
        "key",
        [{"id": "v1", "title": "Game", "released": None, "votecount": None}],
        [_character("c1", "Game", "v1"), _character("c2", "Game", "v1")],
    )

    # 只有 c2 用过 → 应优先抽从未用过的 c1
    waifu_usage.mark_used("c2")
    assert waifu_cache.pick_character("key", lru=True).id == "c1"

    # c1 也用过（且比 c2 晚用）→ 应抽最久未用的 c2
    waifu_usage.mark_used("c1")
    assert waifu_cache.pick_character("key", lru=True).id == "c2"


def test_pick_character_without_lru_stays_random(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(waifu_cache.config, "data_dir", str(tmp_path))
    waifu_cache.add_company_data(
        "smee",
        [{"id": "v1", "title": "Game", "released": None, "votecount": None}],
        [_character("c1", "Game", "v1"), _character("c2", "Game", "v1")],
    )

    picked = waifu_cache.pick_character("smee", lru=False)
    assert picked is not None
    assert picked.id in ("c1", "c2")
