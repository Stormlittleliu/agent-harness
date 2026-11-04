# -*- coding: utf-8 -*-
"""编辑器 P0：三栏工作台、撤销、草稿按场景保留、错误定位。"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core.interfaces.console import routes

ROOT = Path(__file__).resolve().parents[1]
DRAFTS = ROOT / "data" / "runtime" / "spec_drafts"


@pytest.fixture(autouse=True)
def _clean_runtime_drafts():
    DRAFTS.mkdir(parents=True, exist_ok=True)
    for path in DRAFTS.glob("*.json"):
        path.unlink()
    yield
    for path in DRAFTS.glob("*.json"):
        path.unlink()


def _app(scenario: str = "flow_demo", state: dict | None = None) -> AppTest:
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=300)
    app.session_state["console:route"] = routes.Route("build", scenario, "structure")
    for key, value in (state or {}).items():
        app.session_state[key] = value
    app.run()
    return app


def _button(app: AppTest, label: str):
    for button in app.button:
        if str(button.label) == label:
            return button
    raise AssertionError(f"按钮不存在：{label}；实际有 {[b.label for b in app.button]}")


def _nodes(app: AppTest, scenario: str = "flow_demo") -> list[dict]:
    return app.session_state["editor:drafts"][scenario]["workflows"]["qa"]["nodes"]


def test_workbench_has_left_center_right_and_status():
    app = _app()
    assert not app.exception, [item.value for item in app.exception]
    markdown = " ".join(str(item.value) for item in app.markdown)
    assert "块库" in markdown
    assert "检查器" in markdown
    labels = [str(button.label) for button in app.button]
    assert "撤销" in labels
    assert "重做" in labels
    assert "保存为新版本" in labels
    assert "只校验，不保存" in labels


def test_delete_node_can_be_undone():
    app = _app()
    app.session_state["editor-selected"] = "search"
    app.run()
    assert "search" in [node["id"] for node in _nodes(app)]

    _button(app, "删除节点").click().run()
    assert "search" not in [node["id"] for node in _nodes(app)]

    _button(app, "撤销").click().run()
    assert "search" in [node["id"] for node in _nodes(app)]
    assert not app.exception, [item.value for item in app.exception]


def test_draft_survives_scenario_switch():
    app = _app()
    before = len(_nodes(app))
    _button(app, "+ 模型生成").click().run()
    after = len(_nodes(app))
    assert after == before + 1

    app.session_state["console:route"] = routes.Route("build", "workspace_assistant", "structure")
    app.run()
    assert not app.exception, [item.value for item in app.exception]
    app.session_state["console:route"] = routes.Route("build", "flow_demo", "structure")
    app.run()
    assert len(_nodes(app)) == after


def test_parameter_change_can_be_undone():
    app = _app()
    app.session_state["editor-selected"] = "answer"
    app.run()
    node = next(item for item in _nodes(app) if item["id"] == "answer")
    before = node.get("args", {}).get("prompt", "")

    area = next(item for item in app.text_area if str(item.label) == "prompt")
    area.set_value("新的回答指令")
    app.run()
    node = next(item for item in _nodes(app) if item["id"] == "answer")
    assert node["args"]["prompt"] == "新的回答指令"

    _button(app, "撤销").click().run()
    node = next(item for item in _nodes(app) if item["id"] == "answer")
    assert node["args"].get("prompt", "") == before


def test_unsaved_marker_appears_after_add():
    app = _app()
    _button(app, "+ 模型生成").click().run()
    captions = " ".join(str(item.value) for item in app.caption)
    assert "未保存" in captions


def test_error_item_can_locate_node():
    app = _app()
    app.session_state["editor-errors"] = ["workflow[qa].search：缺少输入 tool_result"]
    app.run()
    _button(app, "定位 search").click().run()
    assert app.session_state["editor-selected"] == "search"
    assert not app.exception, [item.value for item in app.exception]
