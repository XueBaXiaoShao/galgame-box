"""配置解析测试。"""

from __future__ import annotations

from galgame_box.config import Config, _env_int_list


def test_from_env_defaults(monkeypatch) -> None:
    monkeypatch.delenv("GALGAME_NSFW", raising=False)
    monkeypatch.delenv("GALGAME_TOUCHGAL_TOKEN", raising=False)
    monkeypatch.delenv("GALGAME_PROXY", raising=False)
    monkeypatch.delenv("GALGAME_REQUEST_TIMEOUT", raising=False)
    monkeypatch.delenv("GALGAME_PUSH_GROUPS", raising=False)
    monkeypatch.delenv("GALGAME_PUSH_TIME", raising=False)

    cfg = Config.from_env()

    assert cfg.nsfw == "sfw"
    assert cfg.touchgal_token == ""
    assert cfg.proxy == ""
    assert cfg.request_timeout == 30
    assert cfg.push_groups == []
    assert cfg.push_time == "07:00"


def test_from_env_values(monkeypatch) -> None:
    monkeypatch.setenv("GALGAME_NSFW", "all")
    monkeypatch.setenv("GALGAME_TOUCHGAL_TOKEN", "tok123")
    monkeypatch.setenv("GALGAME_PROXY", "http://127.0.0.1:7897")
    monkeypatch.setenv("GALGAME_REQUEST_TIMEOUT", "45")
    monkeypatch.setenv("GALGAME_SEARCH_LIMIT", "3")

    cfg = Config.from_env()

    assert cfg.nsfw == "all"
    assert cfg.touchgal_token == "tok123"
    assert cfg.proxy == "http://127.0.0.1:7897"
    assert cfg.request_timeout == 45
    assert cfg.search_limit == 3


def test_env_int_list_supports_comma_and_json(monkeypatch) -> None:
    monkeypatch.setenv("GALGAME_PUSH_GROUPS", "111,222")
    assert _env_int_list("GALGAME_PUSH_GROUPS") == [111, 222]

    monkeypatch.setenv("GALGAME_PUSH_GROUPS", '[333, 444]')
    assert _env_int_list("GALGAME_PUSH_GROUPS") == [333, 444]

    monkeypatch.setenv("GALGAME_PUSH_GROUPS", "bad")
    assert _env_int_list("GALGAME_PUSH_GROUPS") == []


def test_admin_ids_share_x_admin_when_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("GALGAME_ADMIN_IDS", raising=False)
    monkeypatch.setenv("X_ADMIN_IDS", "111,222")
    monkeypatch.delenv("SUPERUSERS", raising=False)

    assert Config.from_env().admin_ids == [111, 222]


def test_admin_ids_prefer_galgame_setting(monkeypatch) -> None:
    monkeypatch.setenv("GALGAME_ADMIN_IDS", "999")
    monkeypatch.setenv("X_ADMIN_IDS", "111,222")

    assert Config.from_env().admin_ids == [999]


def test_admin_ids_fall_back_to_superusers(monkeypatch) -> None:
    monkeypatch.delenv("GALGAME_ADMIN_IDS", raising=False)
    monkeypatch.delenv("X_ADMIN_IDS", raising=False)
    monkeypatch.setenv("SUPERUSERS", '["333"]')

    assert Config.from_env().admin_ids == [333]
