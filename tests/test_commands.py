"""命令入口测试：/shou gal 仅处理 gal 子命令并放行其他 /shou。"""

from __future__ import annotations

from galgame_box import commands


def test_parse_subcommand_english_only() -> None:
    assert commands.parse_subcommand("vn 苍之彼方") == ("vn", "苍之彼方")
    assert commands.parse_subcommand("character 美咲") == ("character", "美咲")
    assert commands.parse_subcommand("producer") == ("producer", "")
    assert commands.parse_subcommand("id v123") == ("id", "v123")
    assert commands.parse_subcommand("event 8-5") == ("event", "8-5")
    assert commands.parse_subcommand("random") == ("random", "")
    assert commands.parse_subcommand("recommend 恋爱 校园") == (
        "recommend",
        "恋爱 校园",
    )
    assert commands.parse_subcommand("download 42") == ("download", "42")
    assert commands.parse_subcommand("find") == ("find", "")
    assert commands.parse_subcommand("") == (None, "")
    # 中文子命令不再支持：未知命令只返回参数，处理器会给出帮助
    assert commands.parse_subcommand("作品 xxx") == (None, "xxx")
    assert commands.parse_subcommand("下载 42") == (None, "42")


def test_shou_gal_matcher_priority_and_blocking() -> None:
    assert commands.shou_gal.priority == 1
    assert commands.shou_gal.block is True


def test_is_gal_event_only_matches_shou_gal() -> None:
    assert commands._is_gal_event(_fake_event("/shou gal")) is True
    assert commands._is_gal_event(_fake_event("/shou gal vn 千恋万花")) is True
    assert commands._is_gal_event(_fake_event("shou gal random")) is True
    assert commands._is_gal_event(_fake_event("/shougal vn x")) is True
    assert commands._is_gal_event(_fake_event("/shou list")) is False
    assert commands._is_gal_event(_fake_event("/shou")) is False
    assert commands._is_gal_event(_fake_event("/shou galaxy")) is False
    assert commands._is_gal_event(_fake_event("你好")) is False


def test_parse_limits_trailing_suffix() -> None:
    assert commands.parse_limits("ムラサメ limits 1") == ("ムラサメ", 1)
    assert commands.parse_limits("千恋万花 limit 3") == ("千恋万花", 3)
    assert commands.parse_limits("key LIMITS 5") == ("key", 5)
    assert commands.parse_limits("无限制") == ("无限制", None)
    assert commands.parse_limits("abc limits 0") == ("abc", None)
    assert commands.parse_limits("abc limits 999") == ("abc", 50)
    assert commands.parse_limits("abc limits 1 extra") == ("abc limits 1 extra", None)


async def test_vn_handler_applies_limits(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []

    async def fake_search(keyword: str, limit: int):
        calls.append((keyword, limit))
        return []

    monkeypatch.setattr(commands.vndb, "search_vn", fake_search)
    await _run(commands._cmd_vn(_FakeMatcher(), "千恋万花", 1))
    assert calls == [("千恋万花", 1)]


async def test_character_handler_defaults_to_config_limit(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []

    async def fake_search(keyword: str, limit: int):
        calls.append((keyword, limit))
        return []

    monkeypatch.setattr(commands.vndb, "search_character", fake_search)
    await _run(commands._cmd_character(_FakeMatcher(), "ムラサメ"))
    assert calls == [("ムラサメ", commands.config.search_limit)]


def test_message_with_image_uses_url_or_base64() -> None:
    url_message = commands._message_with_image(
        "https://img.example/a.jpg", "text"
    )
    assert url_message[0].type == "image"
    assert url_message[0].data["file"] == "https://img.example/a.jpg"

    b64_message = commands._message_with_image("AAAA", "text")
    assert b64_message[0].type == "image"
    assert b64_message[0].data["file"] == "base64://AAAA"

    plain_message = commands._message_with_image(None, "text")
    assert plain_message[0].type == "text"


def _fake_event(text: str):
    class FakeEvent:
        def __init__(self, value: str) -> None:
            self._value = value

        def get_plaintext(self) -> str:
            return self._value

    return FakeEvent(text)


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
