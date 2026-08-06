"""/shou gal 命令入口：作为 /shou 的子命令与 xqq-forwarder 共存。

本插件注册优先级更高的 on_command("shou")，仅在第一个参数为 gal 时处理；
其他 /shou 子命令直接放行给 xqq-forwarder 的 x_admin 插件。
"""

from __future__ import annotations

import base64
import json
import os
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path

from nonebot import logger, on_command
from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent, MessageSegment
from nonebot.matcher import Matcher
from nonebot.params import CommandArg

from . import animetrace, format as fmt, http, permissions, touchgal, vndb, waifu
from .config import config
from .models import VNDBCharacter, VNDBProducer, VNDBVn


def _is_gal_event(event: MessageEvent) -> bool:
    """只放行 /shou gal 开头的消息；其他 /shou 交给 x_admin。"""
    text = (event.get_plaintext() or "").lstrip()
    return re.match(r"^/?shou\s*gal(?:\s|$)", text, re.IGNORECASE) is not None


shou_gal = on_command("shou", rule=_is_gal_event, priority=1, block=True)


def _is_slash_waifu(event: MessageEvent) -> bool:
    """/waifu 简化入口只认带斜杠的命令，避免普通文本误触发。"""
    text = (event.get_plaintext() or "").lstrip()
    return re.match(r"^/waifu(?:\s|$)", text, re.IGNORECASE) is not None


waifu_short = on_command("waifu", rule=_is_slash_waifu, priority=1, block=True)


@waifu_short.handle()
async def handle_waifu_short(
    event: MessageEvent,
    matcher: Matcher,
    arg: Message = CommandArg(),
) -> None:
    """/waifu 简化入口：等价 /shou gal waifu（reroll/set/settings 同样可用）。"""
    value = (arg.extract_plain_text() or "").strip()
    await _cmd_waifu(matcher, event, value)


_LIMITS_RE = re.compile(r"(?i)\blimits?\s+(\d{1,4})\s*$")
_MAX_LIMIT = 50

_SUB_MAP = {
    "vn": "vn",
    "character": "character",
    "producer": "producer",
    "id": "id",
    "event": "event",
    "random": "random",
    "recommend": "recommend",
    "download": "download",
    "find": "find",
    "waifu": "waifu",
}


def parse_subcommand(text: str) -> tuple[str | None, str]:
    """把「作品 xxx」拆成（子命令名, 参数）。"""
    text = (text or "").strip()
    if not text:
        return None, ""
    parts = text.split(maxsplit=1)
    sub = _SUB_MAP.get(parts[0].lower())
    rest = parts[1].strip() if len(parts) > 1 else ""
    return sub, rest


def parse_limits(text: str) -> tuple[str, int | None]:
    """解析尾缀 `limits <N>`；返回（去掉尾缀的文本, 条数或 None）。"""
    text = (text or "").strip()
    match = _LIMITS_RE.search(text)
    if not match:
        return text, None
    limit = int(match.group(1))
    if limit < 1:
        return text[: match.start()].strip(), None
    return text[: match.start()].strip(), min(limit, _MAX_LIMIT)


@shou_gal.handle()
async def handle_shou_gal(
    bot: Bot,
    event: MessageEvent,
    matcher: Matcher,
    arg: Message = CommandArg(),
):
    text = (arg.extract_plain_text() or "").strip()
    parts = text.split(maxsplit=1)
    if not parts or parts[0].lower() != "gal":
        # 非 gal 子命令，放行给 x_admin 处理
        return
    sub, rest = parse_subcommand(parts[1] if len(parts) > 1 else "")
    keyword, limit = parse_limits(rest)

    try:
        if sub is None:
            await matcher.finish(fmt.help_text())
        elif sub == "vn":
            await _cmd_vn(matcher, keyword, limit)
        elif sub == "character":
            await _cmd_character(matcher, keyword, limit)
        elif sub == "producer":
            await _cmd_producer(matcher, keyword, limit)
        elif sub == "id":
            await _cmd_id(matcher, keyword)
        elif sub == "event":
            await _cmd_event(matcher, keyword, limit)
        elif sub == "random":
            await _cmd_random(matcher)
        elif sub == "recommend":
            await _cmd_recommend(matcher, keyword, limit)
        elif sub == "download":
            await _cmd_download(matcher, keyword, limit)
        elif sub == "find":
            await _cmd_find(bot, event, matcher, keyword)
        elif sub == "waifu":
            await _cmd_waifu(matcher, event, keyword)
    except (http.HttpError, RuntimeError, ValueError) as exc:
        logger.warning("galgame-box 命令执行失败：{}", exc)
        await matcher.finish(str(exc))


async def _send_messages(matcher: Matcher, messages: list[Message]) -> None:
    if not messages:
        return
    for message in messages[:-1]:
        await matcher.send(message)
    await matcher.finish(messages[-1])


def _image_segment(url_or_base64: str | None) -> MessageSegment | None:
    if not url_or_base64:
        return None
    if url_or_base64.startswith("http"):
        return MessageSegment.image(url_or_base64)
    return MessageSegment.image(f"base64://{url_or_base64}")


def _message_with_image(image_url: str | None, text: str) -> Message:
    segments: list[MessageSegment] = []
    image = _image_segment(image_url)
    if image is not None:
        segments.append(image)
    segments.append(MessageSegment.text(text))
    return Message(segments)


async def _cmd_vn(matcher: Matcher, keyword: str, limit: int | None = None) -> None:
    if not keyword:
        await matcher.finish("请输入作品名，例如：/shou gal vn 苍之彼方的四重奏")
    items = await vndb.search_vn(keyword, limit or config.search_limit)
    if not items:
        await matcher.finish(f"未搜索到作品：{keyword}")
    messages = [
        _message_with_image(item.image.url if item.image else None, fmt.fmt_vn(item))
        for item in items
    ]
    await _send_messages(matcher, messages)


async def _cmd_character(
    matcher: Matcher, keyword: str, limit: int | None = None
) -> None:
    if not keyword:
        await matcher.finish("请输入角色名，例如：/shou gal character 鸢泽美咲")
    # 默认只返回匹配度最高的第一个结果，避免刷屏；需要更多时用 limits <N> 覆盖
    items = await vndb.search_character(keyword, limit or 1)
    if not items:
        await matcher.finish(f"未搜索到角色：{keyword}")
    messages = [
        _message_with_image(
            item.image.url if item.image else None, fmt.fmt_character(item)
        )
        for item in items
    ]
    await _send_messages(matcher, messages)


async def _cmd_producer(
    matcher: Matcher, keyword: str, limit: int | None = None
) -> None:
    if not keyword:
        await matcher.finish("请输入厂商名，例如：/shou gal producer Key")
    producers = await vndb.search_producer(keyword, limit or 3)
    if not producers:
        await matcher.finish(f"未搜索到厂商：{keyword}")
    messages: list[Message] = []
    for producer in producers:
        vns = await vndb.producer_vns(producer.id, config.producer_vns)
        text = fmt.fmt_producer(producer)
        if vns:
            text += "\n\n代表作品：\n" + "\n\n".join(
                fmt.fmt_vn(vn) for vn in vns
            )
        messages.append(Message(MessageSegment.text(text)))
    await _send_messages(matcher, messages)


async def _cmd_id(matcher: Matcher, value: str) -> None:
    if not value or value[:1].lower() not in "vcp":
        await matcher.finish("请输入 VNDB ID，格式：v123 / c123 / p123")
    result = await vndb.get_by_id(value.lower())
    if isinstance(result, VNDBVn):
        await matcher.finish(
            _message_with_image(
                result.image.url if result.image else None, fmt.fmt_vn(result)
            )
        )
    elif isinstance(result, VNDBCharacter):
        await matcher.finish(
            _message_with_image(
                result.image.url if result.image else None,
                fmt.fmt_character(result),
            )
        )
    else:
        producer, vns = result
        text = fmt.fmt_producer(producer)
        if vns:
            text += "\n\n代表作品：\n" + "\n\n".join(fmt.fmt_vn(vn) for vn in vns)
        await matcher.finish(Message(MessageSegment.text(text)))


async def _cmd_event(
    matcher: Matcher, value: str, limit: int | None = None
) -> None:
    now = datetime.now()
    month, day = now.month, now.day
    if value:
        try:
            separator = "-" if "-" in value else "/"
            month_text, day_text = value.split(separator, 1)
            month, day = int(month_text), int(day_text)
            if not (1 <= month <= 12 and 1 <= day <= 31):
                raise ValueError
        except ValueError:
            await matcher.finish("日期格式错误，应为「月-日」，例如：8-5")

    vns, characters = await vndb.today_events(month, day, config.event_rating)
    show_limit = limit or config.event_limit
    lines = [f"【历史上的今天】{fmt.weekday_text(month, day)}"]
    if vns:
        lines.append("今天发售的作品：")
        for vn in vns[:show_limit]:
            lines.append(fmt.fmt_vn(vn))
    if characters:
        lines.append("今天生日的角色：")
        for character in characters[:show_limit]:
            lines.append(
                fmt.fmt_character(character, with_vns=False, with_name=False)
            )
    if not vns and not characters:
        lines.append("今天没有符合条件的作品或角色。")
    await matcher.finish(Message(MessageSegment.text("\n\n".join(lines))))


async def _cmd_random(matcher: Matcher) -> None:
    unique_id = await touchgal.random_id()
    if not unique_id:
        await matcher.finish("随机获取作品失败，请稍后重试")
    html = await touchgal.page_html(unique_id)
    details = touchgal.parse_details(html)

    search_keyword = details.title
    if not search_keyword and len(details.third_info) > 1:
        search_keyword = details.third_info[1]
    item = None
    if search_keyword:
        items, _ = await touchgal.search(search_keyword, limit=1)
        item = items[0] if items else None

    segments: list[MessageSegment] = []
    if item and item.banner:
        image = _image_segment(item.banner)
        if image is not None:
            segments.append(image)
    lines: list[str] = []
    if item:
        lines.append(fmt.fmt_touchgal(item))
    elif details.title:
        lines.append(f"标题：{details.title}")
    if details.third_info:
        lines.append(f"{details.third_info[0]}：{details.third_info[1]}")
    if details.description:
        lines.append(f"简介：\n{details.description[:500]}")
    for preview in details.previews[:3]:
        image = _image_segment(preview)
        if image is not None:
            segments.append(image)
    segments.append(MessageSegment.text("\n\n".join(lines)))
    await matcher.finish(Message(segments))


async def _cmd_recommend(
    matcher: Matcher, tags: str, limit: int | None = None
) -> None:
    if not tags:
        await matcher.finish(
            "请输入至少一个标签，例如：/shou gal recommend 恋爱 校园"
        )
    items, total = await touchgal.search(
        tags,
        limit=limit or config.recommend_count,
        search_in_tag=True,
        search_in_alias=False,
    )
    if not items:
        await matcher.finish(f"未找到标签「{tags}」相关的作品")
    messages: list[Message] = []
    for item in items:
        messages.append(
            _message_with_image(item.banner, fmt.fmt_touchgal(item))
        )
    messages.append(
        Message(
            MessageSegment.text(
                f"共 {total} 条结果，展示前 {len(items)} 条；"
                "可用 /shou gal download <TouchGal ID> 获取资源。"
            )
        )
    )
    await _send_messages(matcher, messages)


async def _cmd_download(
    matcher: Matcher, value: str, limit: int | None = None
) -> None:
    if not value:
        await matcher.finish(
            "请输入 TouchGal ID / VNDB ID / 关键词，例如：/shou gal download 12345"
        )
    touchgal_id: int | None = None
    if value.isdigit():
        touchgal_id = int(value)
    else:
        items, total = await touchgal.search(value, limit=limit or 6)
        if not items:
            await matcher.finish(f"未找到相关内容：{value}")
        if total == 1 and len(items) == 1:
            touchgal_id = items[0].id
        else:
            messages = [
                _message_with_image(item.banner, fmt.fmt_touchgal(item))
                for item in items
            ]
            messages.append(
                Message(
                    MessageSegment.text(
                        "未识别到 ID，请使用上面任一 TouchGal ID 重新下载："
                        "/shou gal download <TouchGal ID>"
                    )
                )
            )
            await _send_messages(matcher, messages)
            return

    resources = await touchgal.resources(touchgal_id)
    if not resources:
        await matcher.finish("该作品暂无可用资源")
    messages = [
        Message(MessageSegment.text(fmt.fmt_resource(resource)))
        for resource in resources[:20]
    ]
    if len(resources) > 20:
        messages.append(
            Message(MessageSegment.text(f"仅展示前 20 条，共 {len(resources)} 条资源"))
        )
    await _send_messages(matcher, messages)


async def _cmd_find(
    bot: Bot, event: MessageEvent, matcher: Matcher, value: str
) -> None:
    image = await _extract_image(bot, event, value)
    if not image:
        await matcher.finish(
            "未检测到图片：请附带图片链接、在指令中直接发图片，或回复一张图片后使用"
            " /shou gal find"
        )
    result = await animetrace.search_image(image)
    if not result.data:
        await matcher.finish("未识别到角色")

    header = (
        f"识别模型：{animetrace.current_model()}\n"
        f"匹配数：{len(result.data)}   AI图：{'是' if result.ai else '否'}"
    )
    messages = [Message(MessageSegment.text(header))]

    source_bytes: bytes | None = None
    try:
        if image.startswith("http"):
            source_bytes = await http.request(
                "GET", image, res_type="bytes", handle_cf=False
            )
        else:
            source_bytes = base64.b64decode(image)
    except Exception:
        source_bytes = None

    for index, detected in enumerate(result.data, start=1):
        for jndex, info in enumerate(detected.character[: config.find_results]):
            segments: list[MessageSegment] = []
            crop = _crop_box(source_bytes, detected.box)
            if crop:
                segments.append(MessageSegment.image(f"base64://{crop}"))
            lines = [
                f"【匹配 {index}-{jndex + 1}】"
                f"可信度：{'不可' if detected.not_confident else ''}可信",
                f"角色：{info.character}",
                f"作品：{info.work}",
            ]
            found = await vndb.find_character(info.character, info.work)
            if found:
                character = found[0]
                lines.append(
                    "VNDB："
                    + fmt.fmt_character(character, with_name=False).replace("\n", "；")
                )
            else:
                lines.append("VNDB 暂无记录，角色可能并非来自 Gal")
            segments.append(MessageSegment.text("\n".join(lines)))
            messages.append(Message(segments))
    await _send_messages(matcher, messages)


def _waifu_text(record: dict, note: str = "") -> str:
    lines = [
        "【每日老婆】",
        f"老婆：{record.get('original') or record.get('name') or '未知'}",
        f"VNDB ID：{record.get('character_id')}",
    ]
    birthday = record.get("birthday")
    if isinstance(birthday, list) and len(birthday) >= 2:
        lines.append(f"生日：{birthday[0]}月{birthday[1]}日")
    vns = record.get("vns") or []
    if vns:
        vn_list = [f"「{vn.get('title') or '?'}」（{vn.get('id')}）" for vn in vns]
        lines.append(f"出场作品：{'、'.join(vn_list)}")
    if note:
        lines.append(note)
    return "\n".join(lines)


def _is_female_character(character: VNDBCharacter) -> bool:
    """只有对外性别为女性的角色才能当老婆。"""
    return bool(character.sex and character.sex[0] == "f")


async def _cmd_waifu(
    matcher: Matcher, event: MessageEvent, value: str
) -> None:
    """每日老婆：每人每天一次，管理员可 reroll / set / settings。"""
    user_id = int(getattr(event, "user_id", 0))
    value = (value or "").strip()
    command, _, arg = value.partition(" ")
    command = command.lower()

    if command == "settings":
        await _handle_waifu_settings(matcher, event, arg.strip())
        return

    is_admin = permissions.is_admin(user_id)

    if not value:
        existing = waifu.get_today_waifu(user_id)
        if existing:
            await matcher.finish(
                _message_with_image(
                    existing.get("image_url"),
                    _waifu_text(existing, "你今天已经抽过啦，明天再来（重复展示今日老婆）"),
                )
            )
        settings = waifu.load_settings()
        character = await vndb.random_female_character(**settings)
        if character is None:
            await matcher.finish("今天暂时抽不到老婆，请稍后再试")
        record = waifu.save_waifu(user_id, character)
        note = _waifu_filter_note(settings)
        await matcher.finish(
            _message_with_image(record.get("image_url"), _waifu_text(record, note))
        )
        return

    if command == "reroll":
        if not is_admin:
            await matcher.finish("只有管理员可以更换每日老婆")
        settings = waifu.load_settings()
        character = await vndb.random_female_character(**settings)
        if character is None:
            await matcher.finish("更换失败，请稍后再试")
        record = waifu.save_waifu(user_id, character)
        note = _waifu_filter_note(settings)
        await matcher.finish(
            _message_with_image(
                record.get("image_url"),
                _waifu_text(record, "管理员已更换，这是你的新老婆" + (f"\n{note}" if note else "")),
            )
        )
    elif command == "set":
        if not is_admin:
            await matcher.finish("只有管理员可以指定每日老婆")
        keyword = arg.strip()
        if not keyword:
            await matcher.finish("用法：/shou gal waifu set <角色名或VNDB ID>")
        if re.match(r"^c\d+$", keyword, re.IGNORECASE):
            try:
                result = await vndb.get_by_id(keyword.lower())
                character = result if isinstance(result, VNDBCharacter) else None
            except Exception:
                character = None
        else:
            items = await vndb.search_character(keyword, 1)
            character = items[0] if items else None
        if character is None:
            await matcher.finish(f"未找到角色：{keyword}")
        if not _is_female_character(character):
            await matcher.finish(
                f"角色「{character.original or character.name}」不是女性，"
                "不能作为老婆"
            )
        record = waifu.save_waifu(user_id, character)
        await matcher.finish(
            _message_with_image(
                record.get("image_url"),
                _waifu_text(record, "已设置为你的老婆"),
            )
        )
    elif command == "reset":
        if not permissions.is_admin(user_id):
            await matcher.finish("只有管理员可以重置每日老婆")
        target = arg.strip()
        if not target or target.lower() == "all":
            count = waifu.reset_waifu(None)
            await matcher.finish(
                f"已重置全部用户的每日老婆（{count} 人），今天可以重新抽取"
            )
        if target.isdigit():
            count = waifu.reset_waifu(int(target))
            if count:
                await matcher.finish(f"已重置用户 {target} 的每日老婆")
            await matcher.finish(f"用户 {target} 今天还没有每日老婆")
        await matcher.finish("用法：/waifu reset [all|<QQ号>]")
    else:
        await matcher.finish(
            "用法：/shou gal waifu [reroll|set <角色名>|settings|reset [all|<QQ号>]]"
        )


def _waifu_filter_note(settings: dict) -> str:
    """把当前筛选条件拼成提示文本。"""
    parts: list[str] = []
    threshold = settings.get("popular_threshold") or 0
    year_from = settings.get("year_from") or 0
    year_to = settings.get("year_to") or 0
    if threshold:
        parts.append(f"热度≥{threshold}票")
    if year_from or year_to:
        parts.append(f"年代 {year_from or '不限'}-{year_to or '不限'}")
    return "筛选：" + "、".join(parts) if parts else ""


async def _handle_waifu_settings(
    matcher: Matcher, event: MessageEvent, value: str
) -> None:
    """每日老婆筛选设置：热度（VNDB 作品投票数）与年代范围。"""
    user_id = int(getattr(event, "user_id", 0))
    parts = value.split() if value else []
    action = parts[0].lower() if parts else ""

    if not action:
        await matcher.finish(waifu.settings_text(waifu.load_settings()))
    if not permissions.is_admin(user_id):
        await matcher.finish("只有管理员可以修改每日老婆设置")

    settings = waifu.load_settings()
    if action == "popular":
        if len(parts) != 2 or not parts[1].isdigit() or not (0 <= int(parts[1]) <= 100000):
            await matcher.finish(
                "用法：/shou gal waifu settings popular <N>（0=关闭，最大 100000）"
            )
        settings["popular_threshold"] = int(parts[1])
        waifu.save_settings(settings)
        await matcher.finish(
            f"已设置热度阈值：{settings['popular_threshold']}（0=关闭）"
        )
    if action == "year":
        if len(parts) not in (2, 3):
            await matcher.finish(
                "用法：/shou gal waifu settings year <起始年> [结束年]（0=不限）"
            )
        try:
            year_from = int(parts[1])
            year_to = int(parts[2]) if len(parts) == 3 else 0
        except ValueError:
            await matcher.finish("年份必须是数字")
        if not (
            0 <= year_from <= 2100
            and 0 <= year_to <= 2100
            and (year_from == 0 or year_to == 0 or year_from <= year_to)
        ):
            await matcher.finish("年份范围无效（0=不限，且起始年不能大于结束年）")
        settings["year_from"] = year_from
        settings["year_to"] = year_to
        waifu.save_settings(settings)
        await matcher.finish(
            f"已设置年代范围：{year_from or '不限'} - {year_to or '不限'}"
        )
    if action == "reset":
        waifu.save_settings(waifu.default_settings())
        await matcher.finish("每日老婆设置已重置（热度关闭、年代不限）")
    await matcher.finish(
        "用法：/shou gal waifu settings [popular <N>|year <起始年> [结束年]|reset]"
    )


async def _extract_image(
    bot: Bot, event: MessageEvent, value: str
) -> str | None:
    """从命令参数 / 消息图片 / 引用消息中提取图片 URL 或 base64。"""
    if value.startswith("http"):
        return value

    def scan(segments: list) -> str | None:
        for segment in segments:
            if getattr(segment, "type", None) != "image":
                continue
            data = segment.data
            url = data.get("url") or ""
            if url.startswith("http"):
                return url
            file_value = data.get("file") or data.get("path") or ""
            if file_value.startswith("base64://"):
                return file_value[len("base64://") :]
            path = data.get("path") or ""
            if path and os.path.exists(path):
                return base64.b64encode(Path(path).read_bytes()).decode()
        return None

    found = scan(list(event.get_message()))
    if found:
        return found

    for segment in event.get_message():
        if segment.type == "reply":
            try:
                message_id = int(segment.data.get("id", 0))
                replied = await bot.get_msg(message_id=message_id)
                return scan(list(replied.get("message", [])))
            except Exception:
                continue
    return None


def _crop_box(source: bytes | None, box: list[float]) -> str | None:
    """按 AnimeTrace 归一化坐标裁剪检测区域，返回 base64 JPEG。"""
    if not source or len(box) != 4:
        return None
    try:
        from PIL import Image as PILImage

        image = PILImage.open(BytesIO(source))
        width, height = image.size
        left = int(width * box[0])
        top = int(height * box[1])
        right = int(width * box[2])
        bottom = int(height * box[3])
        area = image.crop((left, top, right, bottom)).convert("RGB")
        output = BytesIO()
        area.save(output, format="JPEG", quality=85)
        return base64.b64encode(output.getvalue()).decode()
    except Exception:
        return None
