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


def test_shou_gal_matcher_priority_and_nonblocking() -> None:
    assert commands.shou_gal.priority == 1
    assert commands.shou_gal.block is False


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
