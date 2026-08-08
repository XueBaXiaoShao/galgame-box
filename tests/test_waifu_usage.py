"""waifu LRU 使用记录测试。"""

from __future__ import annotations

from galgame_box import waifu_usage


def test_mark_and_last_used(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(waifu_usage.config, "data_dir", str(tmp_path))

    assert waifu_usage.last_used("c1") is None
    waifu_usage.mark_used("c1")
    assert waifu_usage.last_used("c1") is not None
