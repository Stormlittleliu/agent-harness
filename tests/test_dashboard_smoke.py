# -*- coding: utf-8 -*-
"""控制台冒烟：三个产品的入口、页面渲染与状态隔离。

路由通过 ``session_state['console:route']`` 直接种入——AppTest 没有 URL，
``?app=...`` 在真实浏览器里由 ``routes.parse`` 解析，这里只验证它之后的渲染。
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.interfaces.console import quality, routes
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


def _group(app: AppTest, key: str):
    """导航 / 页签是 segmented_control，AppTest 里暴露成 button_group。"""
    return next(group for group in app.button_group if group.key == key)


def test_default_opens_first_published_entry():
    app = _app()
    _ok(app)
    published = entries.published_names()
    assert published, "至少要有已发布入口，否则对话页只剩空状态"
    # 常规对话页：直接就是会话，不是一排"开始对话"卡片
    assert len(app.chat_input) == 1
    assert "开始对话" not in [button.label for button in app.button]
    first = entries.load_entry(published[0])
    assert any(first.display_title in str(markdown.value) for markdown in app.markdown)


def test_entry_rail_lists_only_published_entries():
    app = _app()
    keys = [str(button.key) for button in app.button if str(button.key or "").startswith("chat-open-")]
    assert sorted(keys) == sorted(f"chat-open-{name}" for name in entries.published_names())
    # 入口列表在内容左列，不再占用 sidebar
    assert not app.sidebar.button


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
    assert not [g for g in app.button_group if str(g.key or "").startswith("chat-starter:")]


def test_chat_shows_starters_for_empty_thread():
    app = _app(routes.Route("chat", "router"))
    _ok(app)
    starters = _group(app, "chat-starter:router")
    assert len(starters.options) > 0


def test_closed_or_missing_entry_is_explained():
    app = _app(routes.Route("chat", "flow_demo"))
    _ok(app)
    assert any("入口" in str(warning.value) for warning in app.warning)


def test_product_switch_uses_top_nav():
    app = _app()
    _ok(app)
    _group(app, "console:product").set_value(["build"])
    app.run()
    _ok(app, "switch")
    assert app.session_state["console:route"].product == "build"
    assert any("场景库" in str(markdown.value) for markdown in app.markdown)


def test_build_library_lists_every_scenario():
    app = _app(routes.Route("build"))
    _ok(app)
    keys = [str(button.key) for button in app.button if str(button.key or "").startswith("build-open-")]
    assert len(keys) == len(library.entries())


def test_build_detail_tabs_and_publish_form():
    app = _app(routes.Route("build", "workspace_assistant"))
    _ok(app)
    tabs = _group(app, "build:tab")
    assert tabs.value == "overview"
    tabs.set_value(["publish"])
    app.run()
    _ok(app, "publish")
    assert "入口标题" in [box.label for box in app.text_input]
    assert any("校验并发布" in button.label for button in app.button)


def test_quality_views_render():
    app = _app(routes.Route("quality"))
    for group, views in quality.VIEW_GROUPS.items():
        _group(app, "quality:group").set_value([group])
        app.run()
        _ok(app, group)
        for view in views:
            _group(app, "quality:view").set_value([view])
            app.run()
            _ok(app, f"{group}/{view}")


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
    next(button for button in app.button if button.key == "chat-open-workspace_assistant").click()
    app.run()
    _ok(app, "switch")
    assert app.session_state["chat:thread:router"] == "web-router"
    assert app.session_state["chat:thread:workspace_assistant"] == "web-workspace"
    assert app.session_state["console:route"].scenario == "workspace_assistant"
