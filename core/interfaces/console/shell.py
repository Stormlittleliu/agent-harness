# -*- coding: utf-8 -*-
"""控制台外壳：三个产品 + 路由分发。

产品不是"同一层的 8 个 tab"，而是三个不同的工作对象：

- 对话：一次会话（用户面，只有已发布的入口）；
- 构建：一个场景（编辑、分析、发布）；
- 质量：一次运行（评测、复核、优化、自检）。

路由只决定"打开哪个产品 / 哪个场景"，不参与任何页面内部状态；所以
换场景不会再把别的页面的筛选、草稿、表格选择一起清掉。
"""
from __future__ import annotations

import os

import streamlit as st

from core.interfaces.console import build, chat, quality, routes
from core.interfaces.dashboard.layout import inject_css

ROUTE_KEY = "console:route"


def current_route() -> routes.Route:
    """本次会话当前路由；首次渲染时从 URL / 环境变量解析。

    之后以 session_state 为准：``st.navigation`` 在 AppTest 里不可用，而
    ``st.query_params`` 在真实浏览器里够用——两者都不适合当运行中的唯一真相。
    """
    if ROUTE_KEY not in st.session_state:
        st.session_state[ROUTE_KEY] = routes.parse(st.query_params, os.environ)
    route = st.session_state[ROUTE_KEY]
    if not isinstance(route, routes.Route):
        route = routes.parse({}, os.environ)
        st.session_state[ROUTE_KEY] = route
    return route


def _product_bar(route: routes.Route) -> None:
    """品牌 + 左对齐的三个产品按钮；当前产品实心。

    注意：页面顶部的 Streamlit header 是固定定位的透明层，按钮如果压在它下面
    会"看得见但点不动"——所以全局 CSS 把 header 隐藏了（见 layout._CSS）。
    """
    brand, *buttons, _spacer = st.columns([2.4, 1, 1, 1, 4.2], vertical_alignment="center")
    brand.markdown("#### 🛠 Agent Harness")
    for column, product in zip(buttons, routes.PRODUCTS):
        active = product == route.product
        if column.button(
            routes.PRODUCT_LABELS[product],
            key=f"console-nav-{product}",
            type="primary" if active else "secondary",
            use_container_width=True,
        ):
            if not active:
                routes.navigate(product)
    if route.unknown_product:
        st.caption(f"未知的产品：`{route.unknown_product}`，已回到对话。")


def run() -> None:
    route = current_route()
    # 对话页需要左栏放入口列表；构建 / 质量不需要侧边栏，收起来更干净。
    st.set_page_config(
        page_title="Agent Harness 控制台",
        page_icon="🛠",
        layout="wide",
        initial_sidebar_state="expanded" if route.product == "chat" else "collapsed",
    )
    inject_css()
    _product_bar(route)
    if route.product == "build":
        build.render(route)
    elif route.product == "quality":
        quality.render(route)
    else:
        chat.render(route)
