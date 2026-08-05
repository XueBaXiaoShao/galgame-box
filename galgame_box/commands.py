"""/shou gal 命令入口：作为 /shou 的子命令与 xqq-forwarder 共存。

本插件注册优先级更高的 on_command("shou")，仅在第一个参数为 gal 时处理；
其他 /shou 子命令直接放行给 xqq-forwarder 的 x_admin 插件。
"""

from __future__ import annotations

import base64
import os
from datetime import datetime
from io import BytesIO
from pathlib import Path

from nonebot import logger, on_command
from nonebot.adapters.onebot.v11 import Bot, Message, MessageEvent, MessageSegment
from nonebot.matcher import Matcher
from nonebot.params import CommandArg

from . import animetrace, format as fmt, http, touchgal, vndb
from .config import config
from .models import VNDBCharacter, VNDBProducer, VNDBVn

shou_gal = on_command("shou", priority=1, block=False)

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

    try:
        if sub is None:
            await matcher.finish(fmt.help_text())
        elif sub == "vn":
            await _cmd_vn(matcher, rest)
        elif sub == "character":
            await _cmd_character(matcher, rest)
        elif sub == "producer":
            await _cmd_producer(matcher, rest)
        elif sub == "id":
            await _cmd_id(matcher, rest)
        elif sub == "event":
            await _cmd_event(matcher, rest)
        elif sub == "random":
            await _cmd_random(matcher)
        elif sub == "recommend":
            await _cmd_recommend(matcher, rest)
        elif sub == "download":
            await _cmd_download(matcher, rest)
        elif sub == "find":
            await _cmd_find(bot, event, matcher, rest)
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


async def _cmd_vn(matcher: Matcher, keyword: str) -> None:
    if not keyword:
        await matcher.finish("请输入作品名，例如：/shou gal vn 苍之彼方的四重奏")
    items = await vndb.search_vn(keyword, config.search_limit)
    if not items:
        await matcher.finish(f"未搜索到作品：{keyword}")
    messages = [
        _message_with_image(item.image.url if item.image else None, fmt.fmt_vn(item))
        for item in items
    ]
    await _send_messages(matcher, messages)


async def _cmd_character(matcher: Matcher, keyword: str) -> None:
    if not keyword:
        await matcher.finish("请输入角色名，例如：/shou gal character 鸢泽美咲")
    items = await vndb.search_character(keyword, config.search_limit)
    if not items:
        await matcher.finish(f"未搜索到角色：{keyword}")
    messages = [
        _message_with_image(
            item.image.url if item.image else None, fmt.fmt_character(item)
        )
        for item in items
    ]
    await _send_messages(matcher, messages)


async def _cmd_producer(matcher: Matcher, keyword: str) -> None:
    if not keyword:
        await matcher.finish("请输入厂商名，例如：/shou gal producer Key")
    producers = await vndb.search_producer(keyword, 3)
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


async def _cmd_event(matcher: Matcher, value: str) -> None:
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
    lines = [f"【历史上的今天】{fmt.weekday_text(month, day)}"]
    if vns:
        lines.append("今天发售的作品：")
        for vn in vns[: config.event_limit]:
            lines.append(fmt.fmt_vn(vn))
    if characters:
        lines.append("今天生日的角色：")
        for character in characters[: config.event_limit]:
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


async def _cmd_recommend(matcher: Matcher, tags: str) -> None:
    if not tags:
        await matcher.finish(
            "请输入至少一个标签，例如：/shou gal recommend 恋爱 校园"
        )
    items, total = await touchgal.search(
        tags,
        limit=config.recommend_count,
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


async def _cmd_download(matcher: Matcher, value: str) -> None:
    if not value:
        await matcher.finish(
            "请输入 TouchGal ID / VNDB ID / 关键词，例如：/shou gal download 12345"
        )
    touchgal_id: int | None = None
    if value.isdigit():
        touchgal_id = int(value)
    else:
        items, total = await touchgal.search(value, limit=6)
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
