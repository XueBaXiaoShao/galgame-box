"""把 VNDB / TouchGal 数据格式化为可读的中文文本。"""

from __future__ import annotations

from datetime import date

from .config import config
from .models import (
    Resource,
    TouchGalItem,
    VNDBCharacter,
    VNDBProducer,
    VNDBVn,
)

LANG = {
    "ja": "日文",
    "en": "英文",
    "zh-Hans": "简中",
    "zh-Hant": "繁中",
    "zh": "中文",
}
DEVELOP_TYPE = {"co": "公司", "in": "个人", "ng": "业余团体"}
GENDER = {"m": "男性", "f": "女性", "b": "双性", "n": "无性"}
WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def _clean(lines: list[str]) -> list[str]:
    return [line for line in lines if line]


def fmt_vn(vn: VNDBVn, *, with_title: bool = True) -> str:
    """格式化 VNDB 作品信息。"""
    lines: list[str] = []
    if with_title:
        lines.append(f"标题：{vn.alttitle or vn.title}")
    lines.append(f"VNDB ID：{vn.id}")
    if vn.titles:
        for item in vn.titles:
            if item.lang in LANG:
                mark = "官方" if item.official else "非官方"
                lines.append(f"{LANG[item.lang]}标题（{mark}）：{item.title}")
    if vn.aliases:
        lines.append(f"别名：{'、'.join(vn.aliases)}")
    if vn.rating is not None:
        lines.append(f"贝叶斯评分：{vn.rating}")
    if vn.average is not None:
        lines.append(f"平均分：{vn.average}")
    if vn.length_minutes:
        lines.append(f"游玩时间：{round(vn.length_minutes / 60, 1)}小时")
    if vn.developers:
        devs = [f"{d.original or d.name}（{d.id}）" for d in vn.developers]
        lines.append(f"制作者（VNDB ID）：{'、'.join(devs)}")
    if vn.released:
        lines.append(f"发布日期：{vn.released}")
    if vn.platforms:
        lines.append(f"支持平台：{'、'.join(vn.platforms)}")
    return "\n".join(_clean(lines))


def fmt_character(
    character: VNDBCharacter,
    *,
    with_name: bool = True,
    with_vns: bool = True,
) -> str:
    """格式化 VNDB 角色信息；额外字段按 GALGAME_CHARACTER_OPTIONS 展示。"""
    lines: list[str] = []
    if with_name:
        lines.append(f"姓名：{character.original or character.name}")
    lines.append(f"VNDB ID：{character.id}")
    if character.aliases:
        lines.append(f"别称：{'、'.join(character.aliases)}")
    if character.birthday:
        lines.append(f"生日：{character.birthday[0]}月{character.birthday[1]}日")

    options = config.character_options or ""
    if "a" in options and character.blood_type:
        lines.append(f"血型：{character.blood_type}")
    if "b" in options and (
        character.weight is not None or character.height is not None
    ):
        height = character.height if character.height is not None else "??"
        weight = character.weight if character.weight is not None else "??"
        lines.append(f"身高/体重（cm/kg）：{height}/{weight}")
    if "c" in options and character.sex:
        lines.append(f"性别：{GENDER.get(character.sex[0], character.sex[0])}")
    if "d" in options and character.sex and len(character.sex) > 1:
        lines.append(f"真实性别：{GENDER.get(character.sex[1], character.sex[1])}")
    if "e" in options and any(
        value is not None
        for value in (character.bust, character.waist, character.hips)
    ):
        bust = character.bust if character.bust is not None else "??"
        waist = character.waist if character.waist is not None else "??"
        hips = character.hips if character.hips is not None else "??"
        lines.append(f"三围：{bust}-{waist}-{hips}")
    if "f" in options and character.cup:
        lines.append(f"罩杯：{character.cup}")

    if with_vns and character.vns:
        vn_list = [
            f"「{vn.alttitle or vn.title}」（{vn.id}）" for vn in character.vns
        ]
        lines.append(f"出场作品（VNDB ID）：{'、'.join(vn_list)}")
    return "\n".join(_clean(lines))


def fmt_producer(producer: VNDBProducer) -> str:
    """格式化 VNDB 厂商信息。"""
    lines = [
        f"厂商：{producer.original or producer.name}",
        f"VNDB ID：{producer.id}",
    ]
    if producer.aliases:
        lines.append(f"别名：{'、'.join(producer.aliases)}")
    if producer.lang in LANG:
        lines.append(f"文本语言：{LANG[producer.lang]}")
    if producer.type in DEVELOP_TYPE:
        lines.append(f"类型：{DEVELOP_TYPE[producer.type]}")
    return "\n".join(_clean(lines))


def fmt_touchgal(item: TouchGalItem) -> str:
    """格式化 TouchGal 搜索结果。"""
    lines = [
        f"标题：{item.name}",
        f"TouchGal ID：{item.id}",
        f"站内评分：{item.average_rating}",
    ]
    if item.tags:
        lines.append(f"标签：{'、'.join(item.tags)}")
    if item.language:
        langs = [LANG.get(lang, lang) for lang in item.language]
        lines.append(f"资源语言：{'、'.join(langs)}")
    if item.type:
        lines.append(f"资源属性：{'、'.join(item.type)}")
    if item.platform:
        lines.append(f"资源平台：{'、'.join(item.platform)}")
    lines.append(f"作品页：https://www.touchgal.ink/{item.unique_id}")
    return "\n".join(_clean(lines))


def fmt_resource(resource: Resource) -> str:
    """格式化 TouchGal 资源下载项。"""
    lines = [
        f"标题：{resource.name}",
        f"类型：{resource.section}",
    ]
    if resource.platform:
        lines.append(f"资源平台：{'、'.join(resource.platform)}")
    if resource.language:
        langs = [LANG.get(lang, lang) for lang in resource.language]
        lines.append(f"资源语言：{'、'.join(langs)}")
    if resource.note:
        lines.append(f"备注：{resource.note}")
    for link in resource.links:
        block = ["----------"]
        if link.storage:
            block.append(f"存储平台：{link.storage}")
        if link.size:
            block.append(f"文件大小：{link.size}")
        if link.content:
            block.append(f"链接：{link.content}")
        if link.code:
            block.append(f"提取码：{link.code}")
        if link.password:
            block.append(f"解压码：{link.password}")
        lines.append("\n".join(block))
    return "\n".join(_clean(lines))


def weekday_text(month: int, day: int) -> str:
    """返回「M月D日 周X」。"""
    weekday = WEEKDAYS[date(2024, month, day).weekday()]
    return f"{month}月{day}日 {weekday}"


def help_text() -> str:
    return """【Galgame百宝盒】
- /shou gal vn <名称> —— 搜索作品
- /shou gal character <名称> —— 搜索角色
- /shou gal producer <名称> —— 搜索厂商
- /shou gal id <VNDB ID> —— 通过 v/c/p 开头的 VNDB ID 查询
- /shou gal event [月-日] —— 历史上的今天发售作品与角色生日
- /shou gal random —— 随机一部 TouchGal 作品
- /shou gal recommend <标签...> —— 按标签推荐作品
- /shou gal download <ID/关键词> —— 获取资源链接
- /shou gal find [图片链接] —— AnimeTrace 角色识别
- /shou gal waifu —— 每日老婆（仅女性角色，每人每天一次；管理员可 waifu
  reroll 换一个，或 waifu set <角色名/c开头的VNDB ID> 指定）
- /shou gal waifu settings —— 查看/修改每日老婆筛选（热度、年代；仅管理员可改）
- /shou gal waifu settings company <会社key,key...> —— 按会社筛选（含旗下品牌，
  off=关闭；可选列表见 settings company）
- /waifu —— 每日老婆简化入口（等价 /shou gal waifu，reroll/set/settings/reset 同样可用）
- /waifu reset [all|<QQ号>] —— 重置每日老婆（全部或单个用户，仅管理员）

搜索类命令（vn/character/producer/event/recommend/download）可在末尾追加
limits <N> 控制本次返回条数，例如：/shou gal character ムラサメ limits 1"""
