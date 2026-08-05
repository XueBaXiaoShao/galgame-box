"""pytest 全局配置：先初始化 NoneBot，避免插件导入顺序问题。"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("GALGAME_NSFW", "sfw")
os.environ.setdefault("GALGAME_PUSH_GROUPS", "")

import nonebot  # noqa: E402

_original_cwd = Path.cwd()
os.chdir(tempfile.gettempdir())
try:
    nonebot.init()
finally:
    os.chdir(_original_cwd)
