# -*- coding: utf-8 -*-
from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.interfaces.agent_dashboard import ENTRY_CHILD, ENTRY_ROUTER

ROOT = Path(__file__).resolve().parents[1]

# 合并评测页后的基础视图；runtime 只在 coding_demo 中出现，另行验证。
VIEWS = [
    "architecture",
    "editor",
    "task",
    "tests",
    "evaluation",
    "review",
    "optimization",
    "catalog",
]


def _radio(app, label: str):
    for radio in app.sidebar.radio:
        if getattr(radio, "label", "") == label:
            return radio
    raise AssertionError(f"sidebar radio 不存在：{label}")


def _selectbox(app, label: str):
    for selectbox in app.selectbox:
        if getattr(selectbox, "label", "") == label:
            return selectbox
    raise AssertionError(f"selectbox 不存在：{label}")


def test_dashboard_starts_without_exception():
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=180)
    app.run()
    assert not app.exception, [item.value for item in app.exception]
    assert _selectbox(app, "入口模式").value == ENTRY_ROUTER
    assert _radio(app, "页面").value == "overview"


def test_each_dashboard_view_renders():
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=180)
    app.run()
    for view in VIEWS:
        _radio(app, "页面").set_value(view)
        app.run()
        assert not app.exception, (view, [item.value for item in app.exception])


def _child_selectbox(app):
    return _selectbox(app, "子场景")


def test_switching_child_scenario_keeps_current_view():
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=180)
    app.run()
    _selectbox(app, "入口模式").set_value(ENTRY_CHILD)
    app.run()
    _radio(app, "页面").set_value("tests")
    app.run()
    assert _radio(app, "页面").value == "tests"

    _child_selectbox(app).set_value("research_assistant")
    app.run()
    assert not app.exception, [item.value for item in app.exception]
    assert _radio(app, "页面").value == "tests"


def test_runtime_view_stays_when_switching_to_scenario_without_runtime():
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=180)
    app.run()
    _selectbox(app, "入口模式").set_value(ENTRY_CHILD)
    app.run()
    _child_selectbox(app).set_value("coding_demo")
    app.run()
    _radio(app, "页面").set_value("runtime")
    app.run()
    assert _radio(app, "页面").value == "runtime"

    _child_selectbox(app).set_value("workspace_assistant")
    app.run()
    assert not app.exception, [item.value for item in app.exception]
    assert _radio(app, "页面").value == "runtime"


def test_evaluation_view_renders_for_child_scenario():
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=180)
    app.run()
    _selectbox(app, "入口模式").set_value(ENTRY_CHILD)
    app.run()
    _child_selectbox(app).set_value("workspace_assistant")
    app.run()
    _radio(app, "页面").set_value("evaluation")
    app.run()
    assert not app.exception, [item.value for item in app.exception]
    assert any(getattr(radio, "label", "") == "评测视图" for radio in app.radio)


def test_evaluation_modes_render():
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=180)
    app.run()
    _radio(app, "页面").set_value("evaluation")
    app.run()
    mode = next(
        radio for radio in app.radio
        if getattr(radio, "label", "") == "评测视图"
    )
    for value in ["成本 / 时延", "公开基准", "评测记录"]:
        mode.set_value(value)
        app.run()
        assert not app.exception, (value, [item.value for item in app.exception])


def test_router_and_child_entry_modes():
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=180)
    app.run()
    _selectbox(app, "入口模式").set_value(ENTRY_CHILD)
    app.run()
    assert not app.exception, [item.value for item in app.exception]
    child = _child_selectbox(app)
    assert child.value == "workspace_assistant"

    _selectbox(app, "入口模式").set_value(ENTRY_ROUTER)
    app.run()
    assert not app.exception, [item.value for item in app.exception]
    assert _radio(app, "页面").value == "overview"
