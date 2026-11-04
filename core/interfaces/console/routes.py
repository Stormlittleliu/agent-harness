# -*- coding: utf-8 -*-
"""控制台路由：三个产品 + 场景 / 页面参数。

为什么用 query 参数而不是 ``st.navigation``：
Streamlit 1.40 的 ``st.navigation`` 在 AppTest 里拿不到子页面元素，
``switch_page`` 也不认 callable 页面（实测只返回空元素）。本仓库的界面测试
全靠 AppTest，所以这里自己解析 URL，把路由收在一个文件里——以后想换成
``/chat``、``/build`` 这种路径，只需要改 ``parse`` 和 ``link``。

路由优先级：query 参数 > 环境变量 > 默认值。
环境变量是给测试、截图和演示脚本用的后门（``AH_CONSOLE_APP`` 等）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

PRODUCTS = ("chat", "build", "quality")
# 导航用纯文字标签：emoji 在 Windows 下渲染不一致，也容易让页签看起来像营销按钮。
PRODUCT_LABELS = {"chat": "对话", "build": "构建", "quality": "质量"}
DEFAULT_PRODUCT = "chat"
ROUTE_KEY = "console:route"


@dataclass(frozen=True)
class Route:
    """当前打开的产品 / 场景 / 页签。"""

    product: str = DEFAULT_PRODUCT
    scenario: str | None = None
    tab: str | None = None
    # 用户手输了不认识的产品名时保留原值，页面可以给一句提示而不是静默跳走。
    unknown_product: str | None = None


def _first(params: Mapping[str, str], env: Mapping[str, str], key: str, env_key: str) -> str:
    value = params.get(key)
    if value is None or str(value).strip() == "":
        value = env.get(env_key)
    return str(value or "").strip()


def parse(params: Mapping[str, str], env: Mapping[str, str] | None = None) -> Route:
    """从 query 参数 / 环境变量解析路由；不认识的产品回落到默认产品。"""
    env = env or {}
    raw_product = _first(params, env, "app", "AH_CONSOLE_APP").lower()
    unknown = raw_product if raw_product and raw_product not in PRODUCTS else None
    product = raw_product if raw_product in PRODUCTS else DEFAULT_PRODUCT
    scenario = _first(params, env, "scenario", "AH_CONSOLE_SCENARIO") or None
    tab = _first(params, env, "tab", "AH_CONSOLE_TAB") or None
    return Route(product=product, scenario=scenario, tab=tab, unknown_product=unknown)


def link(product: str, scenario: str | None = None, tab: str | None = None) -> str:
    """可复制的站内链接（相对当前 host，粘贴到地址栏即可）。"""
    parts = [f"app={product}"]
    if scenario:
        parts.append(f"scenario={scenario}")
    if tab:
        parts.append(f"tab={tab}")
    return "/?" + "&".join(parts)


def set_route(route: Route) -> None:
    """写入当前路由并同步 URL，**不重跑**。

    ``on_change`` 回调里用它：Streamlit 在回调结束后本来就会重跑，再调
    ``st.rerun()`` 只会多一次；而按钮路径仍然走 ``navigate()``。
    """
    import streamlit as st

    st.session_state[ROUTE_KEY] = route
    try:
        params = {"app": route.product}
        if route.scenario:
            params["scenario"] = route.scenario
        if route.tab:
            params["tab"] = route.tab
        st.query_params.clear()
        st.query_params.update(params)
    except Exception:  # noqa: BLE001 - 无 URL 环境（测试）不阻断跳转
        pass


def navigate(product: str, scenario: str | None = None, tab: str | None = None) -> None:
    """按钮路径：切换产品 / 场景，同步 URL 后立刻重跑。

    AppTest 没有 URL，``st.query_params`` 可能不可用——同步失败不影响跳转，
    因为真相在 ``session_state['console:route']``。
    """
    import streamlit as st

    set_route(Route(product=product, scenario=scenario, tab=tab))
    st.rerun()
