# -*- coding: utf-8 -*-
"""控制台冒烟：三个产品的入口、页面渲染与状态隔离。

路由通过 ``session_state['console:route']`` 直接种入——AppTest 没有 URL，
``?app=...`` 在真实浏览器里由 ``routes.parse`` 解析，这里只验证它之后的渲染。
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.interfaces.console import routes
from core.scenarios import entry as entries
from core.scenarios import library

ROOT = Path(__file__).resolve().parents[1]


def _app(route: routes.Route | None = None, state: dict | None = None) -> AppTest:
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=300)
    if route is not None:
        app.session_state["console:route"] = route
    for key, value in (state or {}).items():
        app.session_state[key] = value
    app.run()
    return app


def _ok(app: AppTest, where: str = "") -> None:
    assert not app.exception, (where, [item.value for item in app.exception])


def _radio(app: AppTest, label: str):
    return next(radio for radio in app.radio if radio.label == label)


def test_default_lands_on_chat_gallery():
    app = _app()
    _ok(app)
    published = entries.published_names()
    assert published, "至少要有已发布入口，否则对话页只剩空状态"
    assert [button.label for button in app.button].count("开始对话") == len(published)
    assert any("已发布" in str(caption.value) for caption in app.caption)


def test_chat_gallery_lists_published_only():
    app = _app()
    keys = [str(button.key) for button in app.button if str(button.key or "").startswith("chat-open-")]
    # 卡片按列排布，DOM 顺序不等于入口顺序；比集合即可
    assert sorted(keys) == sorted(f"chat-open-{name}" for name in entries.published_names())


def test_chat_conversation_renders_history():
    app = _app(
        routes.Route("chat", "router"),
        {
            "chat:messages:router": [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好，我是综合助手。", "trace_id": None},
            ],
            "chat:thread:router": "web-test",
        },
    )
    _ok(app)
    assert len(app.chat_input) == 1
    assert any("综合助手。" in str(markdown.value) for markdown in app.markdown)
    assert not [b for b in app.button if str(b.key or "").startswith("chat-starter-")]


def test_chat_shows_starters_for_empty_thread():
    app = _app(routes.Route("chat", "router"))
    _ok(app)
    assert [b for b in app.button if str(b.key or "").startswith("chat-starter-")]


def test_closed_or_missing_entry_is_explained():
    app = _app(routes.Route("chat", "flow_demo"))
    _ok(app)
    assert any("入口" in str(warning.value) for warning in app.warning)


def test_build_library_lists_every_scenario():
    app = _app(routes.Route("build"))
    _ok(app)
    keys = [str(button.key) for button in app.button if str(button.key or "").startswith("build-open-")]
    assert len(keys) == len(library.entries())


def test_build_detail_tabs_and_publish_form():
    app = _app(routes.Route("build", "workspace_assistant"))
    _ok(app)
    tabs = _radio(app, "页签")
    assert tabs.value == "overview"
    tabs.set_value("publish")
    app.run()
    _ok(app, "publish")
    assert "入口标题" in [box.label for box in app.text_input]
    assert any("校验并发布" in button.label for button in app.button)


def test_quality_views_render():
    app = _app(routes.Route("quality"))
    for view in ("评测", "复核", "优化", "数据集", "基准", "成本", "记录"):
        _radio(app, "视图").set_value(view)
        app.run()
        _ok(app, view)


def test_switching_chat_entry_keeps_other_threads():
    app = _app(
        routes.Route("chat", "router"),
        {
            "chat:messages:router": [{"role": "user", "content": "你好"}],
            "chat:thread:router": "web-router",
            "chat:thread:workspace_assistant": "web-workspace",
        },
    )
    _ok(app)
    picker = next(box for box in app.selectbox if box.label == "切换入口")
    picker.set_value("workspace_assistant")
    app.run()
    _ok(app, "switch")
    assert app.session_state["chat:thread:router"] == "web-router"
    assert app.session_state["chat:thread:workspace_assistant"] == "web-workspace"
    assert app.session_state["console:route"].scenario == "workspace_assistant"
