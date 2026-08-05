"""文本格式化测试。"""

from __future__ import annotations

from galgame_box import format as fmt
from galgame_box.models import (
    Developer,
    Resource,
    ResourceLink,
    TouchGalItem,
    VNDBCharacter,
    VNDBVn,
)


def test_fmt_vn() -> None:
    vn = VNDBVn(
        id="v1",
        title="Title",
        alttitle="别名标题",
        rating=8.5,
        average=8.0,
        released="2024-01-01",
        length_minutes=300,
        platforms=["win"],
        developers=[Developer(id="p1", name="Studio")],
    )
    text = fmt.fmt_vn(vn)
    assert "标题：别名标题" in text
    assert "VNDB ID：v1" in text
    assert "贝叶斯评分：8.5" in text
    assert "游玩时间：5.0小时" in text


def test_fmt_character_with_options(monkeypatch) -> None:
    monkeypatch.setattr(fmt.config, "character_options", "abcdef")
    character = VNDBCharacter(
        id="c1",
        name="Hero",
        original="ヒーロー",
        birthday=[8, 5],
        blood_type="A",
        height=160,
        weight=45,
        sex=["f", "m"],
        bust=80,
        waist=55,
        hips=85,
        cup="B",
        aliases=["英雄"],
    )
    text = fmt.fmt_character(character)
    assert "姓名：ヒーロー" in text
    assert "生日：8月5日" in text
    assert "血型：A" in text
    assert "身高/体重（cm/kg）：160/45" in text
    assert "三围：80-55-85" in text
    assert "罩杯：B" in text


def test_fmt_touchgal() -> None:
    item = TouchGalItem(
        id=9,
        unique_id="u9",
        banner="",
        name="作品",
        tags=["恋爱"],
        language=["ja"],
        average_rating=9.1,
        platform=["windows"],
    )
    text = fmt.fmt_touchgal(item)
    assert "TouchGal ID：9" in text
    assert "站内评分：9.1" in text
    assert "https://www.touchgal.ink/u9" in text


def test_fmt_resource_links() -> None:
    resource = Resource(
        id=1,
        name="资源A",
        section="全年龄",
        links=[
            ResourceLink(
                storage="百度网盘",
                size="1GB",
                content="https://pan.example/1",
                code="abcd",
                password="1234",
            )
        ],
    )
    text = fmt.fmt_resource(resource)
    assert "存储平台：百度网盘" in text
    assert "链接：https://pan.example/1" in text
    assert "提取码：abcd" in text
    assert "解压码：1234" in text


def test_help_text_uses_shou_gal_english_subcommands() -> None:
    text = fmt.help_text()
    assert "/shou gal vn" in text
    assert "/shou gal character" in text
    assert "/shou gal recommend" in text
    assert "旮旯" not in text
