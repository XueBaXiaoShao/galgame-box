"""Galgame百宝盒（NoneBot 版）。

以 /shou gal 作为命令入口，与 xqq-forwarder 的 /shou 管理命令共存。
功能：VNDB 作品/角色/厂商查询、TouchGal 随机/推荐/下载、
AnimeTrace 角色出处识别、每日简讯与定时推送。
"""

from nonebot import logger
from nonebot.plugin import PluginMetadata

from . import commands  # noqa: F401
from .scheduler import setup_daily_push

__plugin_meta__ = PluginMetadata(
    name="Galgame百宝盒",
    description=(
        "整合 VNDB / TouchGal / AnimeTrace：作品角色厂商查询、随机推荐下载、"
        "角色出处识别与每日简讯推送，命令入口 /shou gal"
    ),
    usage=(
        "/shou gal vn <名称>、/shou gal character <名称>、"
        "/shou gal producer <名称>、/shou gal id <VNDB ID>、/shou gal event、"
        "/shou gal random、/shou gal recommend <标签>、"
        "/shou gal download <ID/关键词>、/shou gal find [图片]"
    ),
    type="application",
    homepage="https://github.com/PyuraMazo/astrbot_plugin_galgame_box",
    supported_adapters={"~onebot.v11"},
)

setup_daily_push()
