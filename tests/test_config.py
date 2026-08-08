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


def test_cache_refresh_defaults(monkeypatch) -> None:
    monkeypatch.delenv("GALGAME_CACHE_REFRESH_ENABLED", raising=False)
    monkeypatch.delenv("GALGAME_CACHE_REFRESH_TIME", raising=False)
    monkeypatch.delenv("GALGAME_CACHE_VN_LIMIT", raising=False)

    cfg = Config.from_env()

    assert cfg.cache_refresh_enabled is True
    assert cfg.cache_refresh_time == "04:00"
    assert cfg.cache_vn_limit == 30
