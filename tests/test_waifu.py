"""每日老婆功能测试。"""

from __future__ import annotations

import json

from galgame_box import commands, vndb, waifu
from galgame_box.models import Image, VNDBCharacter


def _character(
    char_id: str = "c1", name: str = "Hero", sex: list[str] | None = None
) -> VNDBCharacter:
    return VNDBCharacter(
        id=char_id,
        name=name,
        original="ヒーロー",
        birthday=[8, 5],
        sex=sex if sex is not None else ["f"],
        image=Image(url="https://s.vndb.org/1.jpg"),
        vns=[{"id": "v1", "title": "Game"}],
    )


def _write_admins(tmp_path, ids: list[int]) -> None:
    (tmp_path / "admin_ids.json").write_text(
        json.dumps({"version": 2, "admins": ids}), encoding="utf-8"
    )


def test_waifu_state_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))

    assert waifu.get_today_waifu(123) is None
    record = waifu.save_waifu(123, _character())

    assert record["character_id"] == "c1"
    assert waifu.get_today_waifu(123)["character_id"] == "c1"


def test_waifu_save_stores_source(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))

    waifu.save_waifu(123, _character("c1"), source="yuzu")
    assert waifu.get_today_waifu(123)["source"] == "yuzu"


def test_waifu_text_shows_name_and_representative_work() -> None:
    record = {
        "original": "ムラサメ",
        "name": "Murasa",
        "vns": [{"id": "v1", "title": "千恋万花"}],
    }

    assert commands._waifu_text(record) == "你今天的老婆是来自「千恋万花」的ムラサメ"


def test_waifu_text_falls_back_to_name_without_work() -> None:
    record = {"original": "", "name": "Hero", "vns": []}

    assert commands._waifu_text(record) == "你今天的老婆是Hero"


def test_waifu_settings_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))

    assert waifu.load_settings() == {
        "popular_threshold": 0,
        "year_from": 0,
        "year_to": 0,
        "pool_companies": [],
        "pool_company_ids": {},
    }
    waifu.save_settings({"popular_threshold": 5000, "year_from": 2000, "year_to": 2010})

    assert waifu.load_settings() == {
        "popular_threshold": 5000,
        "year_from": 2000,
        "year_to": 2010,
        "pool_companies": [],
        "pool_company_ids": {},
    }


def test_waifu_reset_all_and_single(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    waifu.save_waifu(111, _character("c1"))
    waifu.save_waifu(222, _character("c2"))

    assert waifu.reset_waifu(111) == 1
    assert waifu.get_today_waifu(111) is None
    assert waifu.get_today_waifu(222) is not None

    assert waifu.reset_waifu(None) == 1
    assert waifu.get_today_waifu(222) is None
    assert waifu.reset_waifu(None) == 0
    assert waifu.reset_waifu(999) == 0


async def test_random_female_character_retries_empty_pages(monkeypatch) -> None:
    calls = []

    async def fake_post(path, payload):
        calls.append(payload)
        if payload.get("reverse"):
            return {"results": [{"id": "c50000"}]}
        if payload.get("page") is not None:
            # 前两次随机页为空，第三次返回结果
            if sum(1 for p in calls if p.get("page") is not None) < 3:
                return {"results": []}
            return {"results": [_character("c42").model_dump()]}
        return {"results": []}

    monkeypatch.setattr(vndb, "_post", fake_post)
    character = await vndb.random_female_character()

    assert character is not None
    assert character.id == "c42"


async def test_random_female_character_skips_male(monkeypatch) -> None:
    calls = []

    async def fake_post(path, payload):
        calls.append(payload)
        if payload.get("reverse"):
            return {"results": [{"id": "c50000"}]}
        if payload.get("page") is not None:
            male = _character("c1", name="Male", sex=["m"])
            female = _character("c2", name="Female")
            result = male if len([p for p in calls if p.get("page")]) == 1 else female
            return {"results": [result.model_dump()]}
        return {"results": []}

    monkeypatch.setattr(vndb, "_post", fake_post)
    character = await vndb.random_female_character()

    assert character is not None
    assert character.id == "c2"
    assert len([p for p in calls if p.get("page")]) == 2


async def test_waifu_once_per_day(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    picks = [_character("c1"), _character("c2")]
    calls = []

    async def fake_random(**kwargs):
        calls.append(1)
        return picks.pop(0)

    monkeypatch.setattr(vndb, "random_female_character", fake_random)
    event = _FakeEvent(123)
    matcher = _FakeMatcher()

    await _run(commands._cmd_waifu(matcher, event, ""))
    assert len(calls) == 1
    assert "你今天的老婆是来自「Game」的ヒーロー" in str(matcher.sent[-1])

    # 第二次调用不再抽新角色，重复展示今日结果
    await _run(commands._cmd_waifu(matcher, event, ""))
    assert len(calls) == 1
    assert "重复展示今日老婆" in str(matcher.sent[-1])


async def test_waifu_admin_reroll(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])
    picks = [_character("c1"), _character("c2")]

    async def fake_random(**kwargs):
        return picks.pop(0)

    monkeypatch.setattr(vndb, "random_female_character", fake_random)
    matcher = _FakeMatcher()
    # 先正常抽取，管理员再用 reroll 换掉
    await _run(commands._cmd_waifu(matcher, _FakeEvent(999), ""))
    await _run(commands._cmd_waifu(matcher, _FakeEvent(999), "reroll"))

    assert "你今天的老婆是来自「Game」的ヒーロー" in str(matcher.sent[-1])
    assert waifu.get_today_waifu(999)["character_id"] == "c2"


async def test_waifu_non_admin_cannot_reroll(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])
    called = False

    async def fake_random():
        nonlocal called
        called = True
        return _character()

    monkeypatch.setattr(vndb, "random_female_character", fake_random)
    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeEvent(100), "reroll"))

    assert called is False
    assert "只有管理员可以更换每日老婆" in str(matcher.sent[-1])


async def test_waifu_admin_added_via_shou_admin_file(
    monkeypatch, tmp_path
) -> None:
    """通过 /shou admin add 持久化的管理员在 galgame-box 同样生效。"""
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [777])
    called = False

    async def fake_random(**kwargs):
        nonlocal called
        called = True
        return _character("c9")

    monkeypatch.setattr(vndb, "random_female_character", fake_random)
    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeEvent(777), "reroll"))

    assert called is True
    assert "你今天的老婆是来自「Game」的ヒーロー" in str(matcher.sent[-1])


async def test_waifu_admin_set_by_name(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])

    async def fake_search(keyword, limit):
        return [_character("c88", name="ムラサメ")]

    monkeypatch.setattr(vndb, "search_character", fake_search)
    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeEvent(999), "set ムラサメ"))

    assert "你今天的老婆是来自「Game」的ヒーロー" in str(matcher.sent[-1])
    assert waifu.get_today_waifu(999)["character_id"] == "c88"


async def test_waifu_admin_set_by_vndb_id(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])

    async def fake_get_by_id(vndb_id: str):
        return _character("c77", name="指定角色")

    monkeypatch.setattr(vndb, "get_by_id", fake_get_by_id)
    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeEvent(999), "set c77"))

    assert "你今天的老婆是来自「Game」的ヒーロー" in str(matcher.sent[-1])
    assert waifu.get_today_waifu(999)["character_id"] == "c77"


async def test_waifu_admin_set_bypasses_gender_rule(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])

    async def fake_search(keyword, limit):
        return [_character("c66", name="男角色", sex=["m"])]

    monkeypatch.setattr(vndb, "search_character", fake_search)
    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeEvent(999), "set 男角色"))

    assert waifu.get_today_waifu(999)["character_id"] == "c66"


async def test_waifu_admin_sets_other_user(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])

    async def fake_search(keyword, limit):
        return [_character("c88", name="ムラサメ")]

    monkeypatch.setattr(vndb, "search_character", fake_search)
    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeEvent(999), "set 888 ムラサメ"))

    assert waifu.get_today_waifu(888)["character_id"] == "c88"
    assert waifu.get_today_waifu(999) is None
    assert "888" in str(matcher.sent[-1])


async def test_waifu_admin_sets_other_user_by_vndb_id(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])

    async def fake_get_by_id(vndb_id: str):
        return _character("c77", name="指定角色")

    monkeypatch.setattr(vndb, "get_by_id", fake_get_by_id)
    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeEvent(999), "set 888 c77"))

    assert waifu.get_today_waifu(888)["character_id"] == "c77"
    assert "888" in str(matcher.sent[-1])


async def test_waifu_settings_view_open_to_all(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))

    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeEvent(123), "settings"))

    assert "每日老婆设置" in str(matcher.sent[-1])
    assert "热度阈值" in str(matcher.sent[-1])


async def test_waifu_settings_modify_requires_admin(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])

    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeEvent(100), "settings popular 5000"))

    assert "只有管理员可以修改每日老婆设置" in str(matcher.sent[-1])
    assert waifu.load_settings()["popular_threshold"] == 0


async def test_waifu_settings_admin_sets_popularity_and_year(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])
    matcher = _FakeMatcher()

    await _run(
        commands._cmd_waifu(matcher, _FakeEvent(999), "settings popular 5000")
    )
    await _run(
        commands._cmd_waifu(matcher, _FakeEvent(999), "settings year 2000 2010")
    )

    assert waifu.load_settings()["popular_threshold"] == 5000
    assert waifu.load_settings()["year_from"] == 2000
    assert waifu.load_settings()["year_to"] == 2010
    assert "已设置" in str(matcher.sent[-1])


async def test_waifu_settings_admin_reset(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])
    waifu.save_settings({"popular_threshold": 5000, "year_from": 2000, "year_to": 2010})

    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeEvent(999), "settings reset"))

    assert waifu.load_settings() == {
        "popular_threshold": 0,
        "year_from": 0,
        "year_to": 0,
        "pool_companies": [],
        "pool_company_ids": {},
    }


async def test_waifu_draw_uses_settings(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    waifu.save_settings({"popular_threshold": 5000, "year_from": 2000, "year_to": 2010})
    captured: dict = {}

    async def fake_random(**kwargs):
        captured.update(kwargs)
        return _character("c9")

    monkeypatch.setattr(vndb, "random_female_character", fake_random)
    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeEvent(123), ""))

    assert captured == {
        "popular_threshold": 5000,
        "year_from": 2000,
        "year_to": 2010,
        "company_ids": [],
        "cache_key": None,
    }


async def test_waifu_draw_uses_fresh_cache_first(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    from galgame_box import waifu_cache
    from galgame_box.models import Image, VnRef

    waifu_cache.add_company_data(
        "yuzusoft",
        [{"id": "v1", "title": "Game", "released": "2012-01-01", "votecount": 4141}],
        [
            commands.VNDBCharacter(
                id="c1",
                name="Hero",
                original="ヒーロー",
                sex=["f"],
                image=Image(url="https://t.vndb.org/1.jpg"),
                vns=[VnRef(id="v1", title="Game")],
            )
        ],
    )

    async def fake_random(**kwargs):
        raise AssertionError("有新鲜缓存时不应请求 VNDB")

    monkeypatch.setattr(vndb, "random_female_character", fake_random)
    matcher = _FakeMatcher()
    await _run(
        commands._cmd_waifu(
            matcher, _FakeGroupEvent(123, 912875556), "", source="yuzu"
        )
    )

    assert waifu.get_today_waifu(123)["character_id"] == "c1"


async def test_waifu_group_backdoor_sets_company(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])

    async def fake_resolve(search_names):
        return ["p98", "p12215"]

    monkeypatch.setattr(vndb, "resolve_company_ids", fake_resolve)
    matcher = _FakeMatcher()
    await _run(
        commands._cmd_waifu(
            matcher, _FakeEvent(999), "settings group=275770691 kaisha=yuzusoft"
        )
    )

    group = waifu.get_group_company(275770691)
    assert group["companies"] == ["yuzusoft"]
    assert group["company_ids"] == ["p98", "p12215"]
    assert "已设置会社后门" in str(matcher.sent[-1])


async def test_waifu_group_backdoor_requires_admin(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])

    matcher = _FakeMatcher()
    await _run(
        commands._cmd_waifu(
            matcher, _FakeEvent(100), "settings group=275770691 kaisha=yuzusoft"
        )
    )

    assert "只有管理员" in str(matcher.sent[-1])
    assert waifu.get_group_company(275770691)["company_ids"] == []


async def test_waifu_group_backdoor_off(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])
    waifu.save_group_company(
        275770691, ["yuzusoft"], ["p98", "p12215"]
    )

    matcher = _FakeMatcher()
    await _run(
        commands._cmd_waifu(
            matcher, _FakeEvent(999), "settings group=275770691 kaisha=off"
        )
    )

    group = waifu.get_group_company(275770691)
    assert group["companies"] == []
    assert group["company_ids"] == []


async def test_waifu_draw_uses_group_backdoor(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    waifu.save_group_company(275770691, ["yuzusoft"], ["p98", "p12215"])
    captured: dict = {}

    async def fake_random(**kwargs):
        captured.update(kwargs)
        return _character("c9")

    monkeypatch.setattr(vndb, "random_female_character", fake_random)
    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeGroupEvent(123, 275770691), ""))

    assert captured["company_ids"] == ["p98", "p12215"]


async def test_yuzuwaifu_uses_fixed_company_and_ignores_kaisha(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    # 群会社后门设置成别的社，yuzuwaifu 仍应固定柚子社
    waifu.save_group_company(912875556, ["smee"], ["p999"])
    captured: dict = {}

    async def fake_random(**kwargs):
        captured.update(kwargs)
        return _character("c9")

    monkeypatch.setattr(vndb, "random_female_character", fake_random)
    monkeypatch.setattr(
        commands, "_yuzusoft_ids", _FakeAsync(["p98", "p12215"])
    )
    matcher = _FakeMatcher()
    await _run(
        commands._cmd_waifu(
            matcher, _FakeGroupEvent(123, 912875556), "", source="yuzu"
        )
    )

    assert captured["company_ids"] == ["p98", "p12215"]


async def test_waifu_and_yuzuwaifu_share_daily_quota(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    picks = [_character("c1"), _character("c2")]
    calls = []

    async def fake_random(**kwargs):
        calls.append(1)
        return picks.pop(0)

    monkeypatch.setattr(vndb, "random_female_character", fake_random)
    monkeypatch.setattr(commands, "_yuzusoft_ids", _FakeAsync(["p98"]))
    matcher = _FakeMatcher()

    # 先抽普通 waifu
    await _run(commands._cmd_waifu(matcher, _FakeEvent(123), ""))
    assert len(calls) == 1
    # 再抽 yuzuwaifu：不再抽新角色，提示已抽过
    await _run(
        commands._cmd_waifu(matcher, _FakeEvent(123), "", source="yuzu")
    )
    assert len(calls) == 1
    assert "已经抽过" in str(matcher.sent[-1])
    assert waifu.get_today_waifu(123)["source"] == "waifu"

    # 重置后再抽 yuzuwaifu 成功
    waifu.reset_waifu(123)
    await _run(
        commands._cmd_waifu(matcher, _FakeEvent(123), "", source="yuzu")
    )
    assert len(calls) == 2
    assert waifu.get_today_waifu(123)["source"] == "yuzu"


async def test_waifu_draw_mentions_user_in_group(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))

    async def fake_random(**kwargs):
        return _character("c9")

    monkeypatch.setattr(vndb, "random_female_character", fake_random)
    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeGroupEvent(123, 912875556), ""))

    message = matcher.sent[-1]
    assert message[0].type == "at"
    assert int(message[0].data["qq"]) == 123


async def test_waifu_draw_no_mention_in_private(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))

    async def fake_random(**kwargs):
        return _character("c9")

    monkeypatch.setattr(vndb, "random_female_character", fake_random)
    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeEvent(123), ""))

    message = matcher.sent[-1]
    assert message[0].type != "at"


async def test_waifu_set_other_mentions_target(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])

    async def fake_search(keyword, limit):
        return [_character("c88", name="ムラサメ")]

    monkeypatch.setattr(vndb, "search_character", fake_search)
    matcher = _FakeMatcher()
    await _run(
        commands._cmd_waifu(
            matcher, _FakeGroupEvent(999, 912875556), "set 888 ムラサメ"
        )
    )

    message = matcher.sent[-1]
    assert message[0].type == "at"
    assert int(message[0].data["qq"]) == 888


def test_group_year_off_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))

    assert waifu.get_group_year_off(912875556) is False
    waifu.save_group_year_off(912875556, True)
    assert waifu.get_group_year_off(912875556) is True
    # 设置会社后门不应清掉 year_off
    waifu.save_group_company(912875556, ["yuzusoft"], ["p98"])
    assert waifu.get_group_year_off(912875556) is True


def test_group_popular_off_round_trip(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))

    assert waifu.get_group_popular_off(912875556) is False
    waifu.save_group_popular_off(912875556, True)
    assert waifu.get_group_popular_off(912875556) is True
    # 设置会社后门不应清掉 popular_off
    waifu.save_group_company(912875556, ["yuzusoft"], ["p98"])
    assert waifu.get_group_popular_off(912875556) is True


async def test_waifu_group_year_off_switch(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])
    matcher = _FakeMatcher()

    await _run(
        commands._cmd_waifu(
            matcher, _FakeEvent(999), "settings group=912875556 year=off"
        )
    )
    assert "已解除" in str(matcher.sent[-1])
    assert waifu.get_group_year_off(912875556) is True

    await _run(
        commands._cmd_waifu(
            matcher, _FakeEvent(999), "settings group=912875556 year=on"
        )
    )
    assert waifu.get_group_year_off(912875556) is False


async def test_waifu_draw_ignores_year_when_group_off(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    waifu.save_settings({"popular_threshold": 0, "year_from": 2010, "year_to": 0})
    waifu.save_group_company(912875556, ["yuzusoft"], ["p98"])
    waifu.save_group_year_off(912875556, True)
    captured: dict = {}

    async def fake_random(**kwargs):
        captured.update(kwargs)
        return _character("c9")

    monkeypatch.setattr(vndb, "random_female_character", fake_random)
    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeGroupEvent(123, 912875556), ""))

    assert captured["year_from"] == 0
    assert captured["year_to"] == 0
    assert captured["company_ids"] == ["p98"]


async def test_waifu_group_popular_off_switch(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])
    matcher = _FakeMatcher()

    await _run(
        commands._cmd_waifu(
            matcher, _FakeEvent(999), "settings group=912875556 popular=off"
        )
    )
    assert "已解除" in str(matcher.sent[-1])
    assert waifu.get_group_popular_off(912875556) is True

    await _run(
        commands._cmd_waifu(
            matcher, _FakeEvent(999), "settings group=912875556 popular=on"
        )
    )
    assert waifu.get_group_popular_off(912875556) is False


async def test_waifu_draw_ignores_popularity_when_group_off(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    waifu.save_settings({"popular_threshold": 5000, "year_from": 0, "year_to": 0})
    waifu.save_group_company(912875556, ["yuzusoft"], ["p98"])
    waifu.save_group_popular_off(912875556, True)
    captured: dict = {}

    async def fake_random(**kwargs):
        captured.update(kwargs)
        return _character("c9")

    monkeypatch.setattr(vndb, "random_female_character", fake_random)
    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeGroupEvent(123, 912875556), ""))

    assert captured["popular_threshold"] == 0
    assert captured["company_ids"] == ["p98"]


async def test_waifu_draw_uses_global_pool_without_backdoor(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    waifu.save_settings(
        {
            "popular_threshold": 0,
            "year_from": 0,
            "year_to": 0,
            "pool_companies": ["key", "august"],
            "pool_company_ids": {"key": ["p1", "p2"], "august": ["p3"]},
        }
    )
    monkeypatch.setattr(commands.random, "choice", lambda seq: "key")
    captured: dict = {}

    async def fake_random(**kwargs):
        captured.update(kwargs)
        return _character("c9")

    monkeypatch.setattr(vndb, "random_female_character", fake_random)
    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeGroupEvent(123, 912875556), ""))

    assert captured["company_ids"] == ["p1", "p2"]


async def test_waifu_pool_settings_admin(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])

    async def fake_resolve(search_names):
        return [f"p{abs(hash(tuple(search_names))) % 10000}"]

    monkeypatch.setattr(vndb, "resolve_company_ids", fake_resolve)
    matcher = _FakeMatcher()
    await _run(
        commands._cmd_waifu(matcher, _FakeEvent(999), "settings pool set")
    )

    settings = waifu.load_settings()
    assert settings["pool_companies"] == list(commands.companies.WAIFU_POOL_KEYS)
    assert isinstance(settings["pool_company_ids"], dict)
    assert "yuzusoft" in settings["pool_company_ids"]
    assert "已设置全局会社池" in str(matcher.sent[-1])

    await _run(
        commands._cmd_waifu(matcher, _FakeEvent(999), "settings pool off")
    )
    assert waifu.load_settings()["pool_company_ids"] == {}


async def test_waifu_reset_requires_admin(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])
    waifu.save_waifu(100, _character("c1"))

    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeEvent(100), "reset all"))

    assert "只有管理员可以重置每日老婆" in str(matcher.sent[-1])
    assert waifu.get_today_waifu(100) is not None


async def test_waifu_admin_reset_all(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])
    waifu.save_waifu(111, _character("c1"))
    waifu.save_waifu(222, _character("c2"))

    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeEvent(999), "reset all"))

    assert "已重置全部" in str(matcher.sent[-1])
    assert waifu.get_today_waifu(111) is None
    assert waifu.get_today_waifu(222) is None


async def test_waifu_admin_reset_single(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(commands.config, "data_dir", str(tmp_path))
    _write_admins(tmp_path, [999])
    waifu.save_waifu(111, _character("c1"))
    waifu.save_waifu(222, _character("c2"))

    matcher = _FakeMatcher()
    await _run(commands._cmd_waifu(matcher, _FakeEvent(999), "reset 111"))

    assert "已重置用户 111" in str(matcher.sent[-1])
    assert waifu.get_today_waifu(111) is None
    assert waifu.get_today_waifu(222) is not None


def test_parse_subcommand_waifu() -> None:
    assert commands.parse_subcommand("waifu") == ("waifu", "")
    assert commands.parse_subcommand("waifu reroll") == ("waifu", "reroll")


class _FakeEvent:
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id


class _FakeGroupEvent(_FakeEvent):
    def __init__(self, user_id: int, group_id: int) -> None:
        super().__init__(user_id)
        self.group_id = group_id


class _FakeAsync:
    def __init__(self, value) -> None:
        self._value = value

    async def __call__(self, *args, **kwargs):
        return self._value


class _FakeMatcher:
    def __init__(self) -> None:
        self.sent: list = []

    async def send(self, message) -> None:
        self.sent.append(message)

    async def finish(self, message=None) -> None:
        if message is not None:
            self.sent.append(message)
        raise _Stop()


class _Stop(Exception):
    """模拟真实 matcher.finish 中断执行。"""


async def _run(coro) -> None:
    try:
        await coro
    except _Stop:
        pass
