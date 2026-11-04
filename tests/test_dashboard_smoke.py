# -*- coding: utf-8 -*-
"""控制台界面冒烟：场景库作为唯一入口，逐页面渲染。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.scenarios import library

ROOT = Path(__file__).resolve().parents[1]

# 除 runtime 外的基础页面；runtime 只在 coding_demo 出现，另行验证。
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
    scenario = _selectbox(app, "场景")
    assert scenario.value == library.default_name()
    assert _radio(app, "页面").value == "overview"


def test_scenario_list_matches_library():
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=180)
    app.run()
    scenario = _selectbox(app, "场景")
    assert list(scenario.options) == [library.label(name) for name in library.names()]


def test_each_dashboard_view_renders():
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=180)
    app.run()
    for view in VIEWS:
        _radio(app, "页面").set_value(view)
        app.run()
        assert not app.exception, (view, [item.value for item in app.exception])


def test_switching_scenario_keeps_current_view():
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=180)
    app.run()
    _radio(app, "页面").set_value("tests")
    app.run()
    assert _radio(app, "页面").value == "tests"

    _selectbox(app, "场景").set_value("research_assistant")
    app.run()
    assert not app.exception, [item.value for item in app.exception]
    assert _radio(app, "页面").value == "tests"


def test_router_is_just_a_scenario():
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=180)
    app.run()
    _selectbox(app, "场景").set_value("router")
    app.run()
    assert not app.exception, [item.value for item in app.exception]
    assert _selectbox(app, "场景").value == "router"
    # 没有任何"入口模式 / 子场景"这种顶层二选一了
    labels = [getattr(box, "label", "") for box in app.selectbox]
    assert "入口模式" not in labels
    assert "子场景" not in labels


def test_runtime_view_stays_when_switching_to_scenario_without_runtime():
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=180)
    app.run()
    _selectbox(app, "场景").set_value("coding_demo")
    app.run()
    _radio(app, "页面").set_value("runtime")
    app.run()
    assert _radio(app, "页面").value == "runtime"

    _selectbox(app, "场景").set_value("workspace_assistant")
    app.run()
    assert not app.exception, [item.value for item in app.exception]
    assert _radio(app, "页面").value == "runtime"


def test_evaluation_view_renders_for_scenario():
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=180)
    app.run()
    _selectbox(app, "场景").set_value("workspace_assistant")
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
