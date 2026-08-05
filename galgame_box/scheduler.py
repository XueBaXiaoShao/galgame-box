"""每日简讯推送：向 GALGAME_PUSH_GROUPS 定时发送今日 Gal 事件。"""

from __future__ import annotations

from datetime import datetime

from nonebot import get_bots, logger

from . import format as fmt, vndb
from .config import config


def setup_daily_push() -> bool:
    """注册每日定时任务；未配置推送群或缺少 apscheduler 时返回 False。"""
    if not config.push_groups:
        logger.info("GALGAME_PUSH_GROUPS 为空，不注册每日简讯推送")
        return False
    try:
        hour_text, minute_text = config.push_time.replace("：", ":").split(":", 1)
        hour, minute = int(hour_text), int(minute_text)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except ValueError:
        logger.error("GALGAME_PUSH_TIME 格式错误：{}", config.push_time)
        return False

    try:
        from nonebot import require

        require("nonebot_plugin_apscheduler")
        from nonebot_plugin_apscheduler import scheduler
    except Exception as exc:
        logger.warning(
            "未加载 nonebot-plugin-apscheduler，每日推送不可用（{}）", exc
        )
        return False

    @scheduler.scheduled_job(
        "cron",
        hour=hour,
        minute=minute,
        id="galgame_daily_push",
        replace_existing=True,
        misfire_grace_time=120,
    )
    async def _push_today() -> None:
        bots = get_bots()
        if not bots:
            logger.warning("galgame-box 每日推送：暂无可用 Bot")
            return
        now = datetime.now()
        vns, characters = await vndb.today_events(
            now.month, now.day, config.event_rating
        )
        lines = [f"【历史上的今天】{fmt.weekday_text(now.month, now.day)}"]
        if vns:
            lines.append("今天发售的作品：")
            lines.extend(fmt.fmt_vn(vn) for vn in vns[: config.event_limit])
        if characters:
            lines.append("今天生日的角色：")
            lines.extend(
                fmt.fmt_character(character, with_vns=False, with_name=False)
                for character in characters[: config.event_limit]
            )
        if not vns and not characters:
            lines.append("今天没有符合条件的作品或角色。")
        message = "\n\n".join(lines)
        for bot in bots.values():
            for group_id in config.push_groups:
                try:
                    await bot.send_group_msg(group_id=group_id, message=message)
                except Exception as exc:
                    logger.warning(
                        "galgame-box 每日推送失败：群 {}（{}）", group_id, exc
                    )

    logger.info(
        "galgame-box 每日简讯推送已注册：{} → {} 个群",
        config.push_time,
        len(config.push_groups),
    )
    return True
