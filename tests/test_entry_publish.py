# -*- coding: utf-8 -*-
"""对话入口：发布校验、发布 / 撤回、结构漂移检测。

用临时目录造一个最小 spec，避免动到真实场景数据。
"""
import json
from pathlib import Path

import pytest

from core.scenarios import entry


def _write_spec(root: Path, name: str, description: str = "演示场景") -> None:
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    spec = {
        "schema_version": 1,
        "name": name,
        "description": description,
        "kind": "agent",
        "tools": [],
        "system_prompt": "你是一个演示场景。",
        "harness": {},
        "workflows": {},
    }
    (directory / "v1.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8", newline="\n")
    (directory / "active.json").write_text(
        json.dumps({"version": 1, "file": "v1.json"}), encoding="utf-8", newline="\n"
    )


def test_publish_requires_a_spec(tmp_path):
    assert entry.validate("ghost", tmp_path) != []
    with pytest.raises(entry.EntryError):
        entry.publish("ghost", root=tmp_path)
    assert not entry.entry_path("ghost", tmp_path).exists()


def test_publish_then_unpublish(tmp_path):
    _write_spec(tmp_path, "demo")
    assert entry.validate("demo", tmp_path) == []

    published = entry.publish(
        "demo",
        title="演示入口",
        tagline="一句话",
        starters=["你好"],
        order=5,
        root=tmp_path,
    )
    assert published.enabled
    assert entry.published_names(tmp_path) == ["demo"]
    assert entry.load_entry("demo", tmp_path).display_title == "演示入口"

    entry.unpublish("demo", tmp_path)
    assert entry.published_names(tmp_path) == []
    # 撤回只关入口，产品信息还在
    assert entry.load_entry("demo", tmp_path).title == "演示入口"


def test_publish_rejects_empty_description(tmp_path):
    _write_spec(tmp_path, "demo", description="  ")
    errors = entry.validate("demo", tmp_path)
    assert any("描述" in error for error in errors)
    with pytest.raises(entry.EntryError):
        entry.publish("demo", root=tmp_path)
    assert not entry.entry_path("demo", tmp_path).exists()


def test_publish_rejects_missing_tool(tmp_path):
    _write_spec(tmp_path, "demo")
    path = tmp_path / "demo" / "v1.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    spec["tools"] = ["not_a_real_tool"]
    path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8", newline="\n")
    errors = entry.validate("demo", tmp_path)
    assert any("not_a_real_tool" in error for error in errors)


def test_drift_is_detected_after_structure_changes(tmp_path):
    _write_spec(tmp_path, "demo")
    entry.publish("demo", title="演示", root=tmp_path)
    assert entry.drifted("demo", tmp_path) is False

    _write_spec(tmp_path, "demo", description="改了描述")
    assert entry.drifted("demo", tmp_path) is True
    # 入口仍可用：漂移只是提醒，不是下线
    assert entry.published_names(tmp_path) == ["demo"]


def test_published_order_follows_entry_order(tmp_path):
    for name in ("later", "first"):
        _write_spec(tmp_path, name)
        entry.publish(name, order=90 if name == "later" else 10, root=tmp_path)
    assert entry.published_names(tmp_path) == ["first", "later"]


def test_missing_active_spec_hides_entry(tmp_path):
    _write_spec(tmp_path, "demo")
    entry.publish("demo", root=tmp_path)
    (tmp_path / "demo" / "active.json").unlink()
    assert entry.published_names(tmp_path) == []
