# -*- coding: utf-8 -*-
"""场景编辑视图的界面级冒烟：能列场景、能渲染画布与表单、校验不写盘。"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.interfaces.dashboard.editor import MODE_CANVAS, MODE_FORM

ROOT = Path(__file__).resolve().parents[1]


def _editor_app() -> AppTest:
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=180)
    app.run()
    for radio in app.sidebar.radio:
        if getattr(radio, "label", "") == "页面":
            radio.set_value("editor")
            break
    app.run()
    return app


def _labels(widgets) -> list[str]:
    return [str(getattr(widget, "label", "")) for widget in widgets]


def _button(app: AppTest, label: str):
    for button in app.button:
        if str(getattr(button, "label", "")) == label:
            return button
    raise AssertionError(f"按钮不存在：{label}；实际有 {_labels(app.button)}")


def _mode_radio(app: AppTest):
    for radio in app.radio:
        if str(getattr(radio, "label", "")) == "编辑方式":
            return radio
    raise AssertionError(f"编辑方式 radio 不存在：{_labels(app.radio)}")


def _spec_files() -> list[Path]:
    return sorted((ROOT / "data" / "specs" / "flow_demo").glob("v*.json"))


def test_editor_lists_spec_scenarios():
    app = _editor_app()
    assert not app.exception, [item.value for item in app.exception]
    tables = [str(frame.value) for frame in app.dataframe]
    assert any("flow_demo" in table for table in tables), tables


def test_editor_defaults_to_canvas_mode():
    app = _editor_app()
    assert not app.exception, [item.value for item in app.exception]
    assert _mode_radio(app).value == MODE_CANVAS
    assert "重新自动排版" in _labels(app.button)


def test_editor_form_mode_shows_node_widgets():
    app = _editor_app()
    _mode_radio(app).set_value(MODE_FORM)
    app.run()
    assert not app.exception, [item.value for item in app.exception]
    labels = _labels(app.text_input) + _labels(app.text_area)
    assert "场景描述" in labels
    assert "系统提示词" in labels
    assert "节点 id" in labels  # 每个节点一个
    assert any(getattr(box, "label", "") == "工作流" for box in app.selectbox)


def test_editor_validate_button_does_not_write():
    before = _spec_files()
    app = _editor_app()
    _button(app, "只校验，不保存").click().run()
    assert not app.exception, [item.value for item in app.exception]
    assert not app.error, [item.value for item in app.error]
    assert _spec_files() == before
