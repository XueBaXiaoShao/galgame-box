"""AnimeTrace 客户端测试。"""

from __future__ import annotations

import pytest

from galgame_box import animetrace, http


@pytest.fixture
def fake_request(monkeypatch):
    calls = []

    async def fake_request(method, url, *, json=None, **kwargs):
        calls.append((url, json))
        return responses[url]

    responses: dict = {}
    monkeypatch.setattr(http, "request", fake_request)
    return calls, responses


async def test_select_model_picks_enabled(fake_request) -> None:
    calls, responses = fake_request
    responses["https://api.animetrace.com/v1/model/list"] = {
        "message": "success",
        "data": [
            {"id": "m1", "enabled": False},
            {"id": "m2", "enabled": True},
        ],
    }
    assert await animetrace.select_model() == "m2"
    assert animetrace._current_model == "m2"


async def test_search_image_retries_on_17703(fake_request) -> None:
    calls, responses = fake_request
    responses["https://api.animetrace.com/v1/model/list"] = {
        "message": "success",
        "data": [{"id": "m2", "enabled": True}],
    }
    responses["https://api.animetrace.com/v1/search"] = {"code": 17703}

    animetrace._current_model = "m1"
    with pytest.raises(RuntimeError):
        await animetrace.search_image("base64data")
    # 第一次 17703 后应重新选择模型并再请求一次，第二次仍失败才抛出
    search_calls = [c for c in calls if c[0].endswith("/v1/search")]
    assert len(search_calls) == 2
