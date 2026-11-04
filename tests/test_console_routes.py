# -*- coding: utf-8 -*-
"""路由解析：三个产品 + 场景 / 页签，与 URL、环境变量的优先级。"""
from core.interfaces.console import routes


def test_default_is_chat():
    route = routes.parse({})
    assert route.product == "chat"
    assert route.scenario is None
    assert route.tab is None


def test_query_params_win_over_env():
    env = {"AH_CONSOLE_APP": "quality", "AH_CONSOLE_SCENARIO": "general"}
    route = routes.parse({"app": "build", "scenario": "router", "tab": "publish"}, env)
    assert route == routes.Route(product="build", scenario="router", tab="publish")


def test_env_is_the_test_backdoor():
    route = routes.parse({}, {"AH_CONSOLE_APP": "build", "AH_CONSOLE_SCENARIO": "flow_demo"})
    assert route.product == "build"
    assert route.scenario == "flow_demo"


def test_unknown_product_falls_back_with_a_note():
    route = routes.parse({"app": "chatroom"})
    assert route.product == "chat"
    assert route.unknown_product == "chatroom"


def test_empty_values_are_treated_as_absent():
    route = routes.parse({"app": "  ", "scenario": "", "tab": "  "})
    assert route.product == "chat"
    assert route.scenario is None
    assert route.tab is None


def test_links_are_shareable():
    assert routes.link("chat", "router") == "/?app=chat&scenario=router"
    assert routes.link("build", "flow_demo", "publish") == "/?app=build&scenario=flow_demo&tab=publish"
    assert routes.link("quality") == "/?app=quality"
