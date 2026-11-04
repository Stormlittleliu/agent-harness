# -*- coding: utf-8 -*-
"""顶部导航 / 页签层级：产品切换、深链、route 作为唯一真相、CSS 契约。

P0 只覆盖导航与页签，不涉及各业务页的内容；这里用 AppTest 走真实入口，
CSS 用文本契约防止「把 pointer-events 和 padding 改回去」这类回退。
"""
from pathlib import Path

from streamlit.testing.v1 import AppTest

from core.interfaces.console import routes
from core.interfaces.dashboard import layout

ROOT = Path(__file__).resolve().parents[1]


def _app(route: routes.Route | None = None) -> AppTest:
    app = AppTest.from_file(str(ROOT / "app_agent.py"), default_timeout=300)
    if route is not None:
        app.session_state["console:route"] = route
    app.run()
    return app


def _group(app: AppTest, key: str):
    return next(group for group in app.button_group if group.key == key)


def _ok(app: AppTest, where: str = "") -> None:
    assert not app.exception, (where, [item.value for item in app.exception])


def test_product_nav_is_one_segmented_control():
    app = _app()
    _ok(app)
    nav = [group for group in app.button_group if group.key == "console:product"]
    assert len(nav) == 1
    assert [option.content for option in nav[0].options] == ["对话", "构建", "质量"]
    # 旧的三按钮导航已经不存在
    assert not [button for button in app.button if str(button.key or "").startswith("console-nav-")]


def test_product_switch_writes_route():
    app = _app()
    _group(app, "console:product").set_value(["quality"])
    app.run()
    _ok(app)
    assert app.session_state["console:route"].product == "quality"
    assert len([group for group in app.button_group if group.key == "console:product"]) == 1


def test_deep_link_tab_publish_opens_publish_form():
    app = _app(routes.Route("build", "workspace_assistant", "publish"))
    _ok(app)
    assert app.session_state["console:route"].tab == "publish"
    assert _group(app, "build:tab").value == "publish"
    assert "入口标题" in [box.label for box in app.text_input]


def test_tab_click_writes_back_route():
    app = _app(routes.Route("build", "workspace_assistant"))
    _group(app, "build:tab").set_value(["tools"])
    app.run()
    _ok(app)
    assert app.session_state["console:route"].tab == "tools"
    _group(app, "build:tab").set_value(["publish"])
    app.run()
    _ok(app)
    assert app.session_state["console:route"].tab == "publish"
    assert "入口标题" in [box.label for box in app.text_input]


def test_route_wins_over_stale_tab_widget():
    app = _app(routes.Route("build", "workspace_assistant", "publish"))
    _group(app, "build:tab").set_value(["overview"])
    app.run()
    assert app.session_state["console:route"].tab == "overview"
    # 模拟"从别处跳回发布"：路由先变，旧 widget 值不能压过它
    app.session_state["console:route"] = routes.Route("build", "workspace_assistant", "publish")
    app.run()
    _ok(app)
    assert _group(app, "build:tab").value == "publish"
    assert "入口标题" in [box.label for box in app.text_input]


def test_chat_rail_lives_in_content_not_sidebar():
    app = _app()
    _ok(app)
    assert not app.sidebar.button
    assert any(str(button.key or "").startswith("chat-open-") for button in app.button)


def test_nav_css_contract():
    css = layout._CSS
    header_rule = css.split('header[data-testid="stHeader"]', 1)[1].split("}", 1)[0]
    assert "pointer-events: none" in header_rule
    assert "padding-top: 5.5rem" in css
    nav_rule = css.split(".st-key-ah-nav", 1)[1].split("}", 1)[0]
    assert "position: fixed" in nav_rule
    assert "top: 0" in nav_rule
    assert "stBaseButton-segmented_controlActive" in css
