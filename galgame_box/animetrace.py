"""AnimeTrace 角色识别 API 客户端。"""

from __future__ import annotations

from . import http
from .models import AnimeTraceResult

SEARCH_URL = "https://api.animetrace.com/v1/search"
MODEL_URL = "https://api.animetrace.com/v1/model/list"

_current_model = ""


async def select_model() -> str:
    """选择一个启用的识别模型。"""
    global _current_model
    resp = await http.request("GET", MODEL_URL, res_type="json")
    if resp.get("message") != "success":
        raise RuntimeError(resp.get("message", "模型获取失败"))
    for model in resp.get("data", []):
        if model.get("enabled"):
            _current_model = str(model["id"])
            return _current_model
    raise RuntimeError("无可用识别模型")


async def search_image(url_or_base64: str) -> AnimeTraceResult:
    """识别图片中的角色；url 传图片链接，否则传裸 base64。"""
    if not _current_model:
        await select_model()
    return await _search(url_or_base64, retried=False)


async def _search(url_or_base64: str, retried: bool) -> AnimeTraceResult:
    if url_or_base64.startswith("http"):
        payload = {"model": _current_model, "ai_detect": 1, "url": url_or_base64}
    else:
        payload = {"model": _current_model, "ai_detect": 1, "base64": url_or_base64}
    resp = await http.request("POST", SEARCH_URL, json=payload, res_type="json")
    code = int(resp.get("code", 400))
    # 17703：当前模型不可用，重新选择后重试一次
    if code == 17703 and not retried:
        await select_model()
        return await _search(url_or_base64, retried=True)
    if code not in (200, 0):
        raise RuntimeError(resp.get("zh_message") or f"识别失败（{code}）")
    return AnimeTraceResult.model_validate(resp)
