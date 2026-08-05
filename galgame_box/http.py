"""通用异步 HTTP 客户端：超时、重试、代理，以及 TouchGal 的 Cloudflare 降级。"""

from __future__ import annotations

import asyncio
from typing import Any, Literal

import httpx

from .config import config

ResType = Literal["json", "text", "bytes"]


class HttpError(RuntimeError):
    """网络请求最终失败。"""


class _CloudflareBlocked(Exception):
    pass


def _client_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "timeout": httpx.Timeout(config.request_timeout),
        "follow_redirects": True,
    }
    if config.proxy:
        kwargs["proxy"] = config.proxy
    return kwargs


async def request(
    method: str,
    url: str,
    *,
    json: dict | None = None,
    params: dict | None = None,
    headers: dict | None = None,
    cookies: dict | None = None,
    res_type: ResType = "json",
    handle_cf: bool = False,
) -> Any:
    """发起请求；`handle_cf=True` 时遇到 Cloudflare 拦截会尝试 curl_cffi 降级。"""
    last_error: Exception | None = None
    attempts = max(1, config.request_retries)
    for index in range(attempts):
        try:
            async with httpx.AsyncClient(**_client_kwargs()) as client:
                response = await client.request(
                    method,
                    url,
                    json=json,
                    params=params,
                    headers=headers,
                    cookies=cookies,
                )
                if handle_cf and response.status_code in (403, 503):
                    raise _CloudflareBlocked(f"Cloudflare {response.status_code}")
                response.raise_for_status()
                if res_type == "json":
                    return response.json()
                if res_type == "bytes":
                    return response.content
                return response.text
        except (httpx.HTTPError, _CloudflareBlocked) as exc:
            last_error = exc
            if index + 1 < attempts:
                await asyncio.sleep(0.5 * (index + 1))

    if handle_cf:
        try:
            return await _cf_request(
                method,
                url,
                json=json,
                params=params,
                headers=headers,
                cookies=cookies,
                res_type=res_type,
            )
        except ImportError:
            pass
        except Exception as exc:  # curl_cffi 自身失败同样视为网络错误
            last_error = exc

    raise HttpError(f"网络请求失败：{url}（{last_error}）")


async def _cf_request(
    method: str,
    url: str,
    *,
    json: dict | None,
    params: dict | None,
    headers: dict | None,
    cookies: dict | None,
    res_type: ResType,
) -> Any:
    """使用 curl_cffi 模拟浏览器 TLS 指纹绕过 Cloudflare。"""
    from curl_cffi.requests import AsyncSession

    async with AsyncSession(impersonate=config.tls) as session:
        response = await session.request(
            method,
            url,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
        )
        if res_type == "json":
            return response.json()
        if res_type == "bytes":
            return response.content
        return response.text
