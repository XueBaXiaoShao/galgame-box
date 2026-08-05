"""统一权限文件读取测试：权限组只存在于 admin_ids.json。"""

from __future__ import annotations

import json

from galgame_box import permissions


def test_is_admin_reads_shared_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(permissions.config, "data_dir", str(tmp_path))
    (tmp_path / "admin_ids.json").write_text(
        json.dumps({"version": 2, "admins": [777, 888]}), encoding="utf-8"
    )

    assert permissions.is_admin(777) is True
    assert permissions.is_admin(888) is True
    assert permissions.is_admin(999) is False


def test_is_admin_without_file_means_no_admins(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(permissions.config, "data_dir", str(tmp_path))

    assert permissions.is_admin(777) is False


def test_is_admin_ignores_bad_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(permissions.config, "data_dir", str(tmp_path))
    (tmp_path / "admin_ids.json").write_text("{bad", encoding="utf-8")

    assert permissions.is_admin(777) is False
