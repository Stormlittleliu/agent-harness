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
from core.interfaces.dashboard.layout import inject_css, sync_widget

ROUTE_KEY = routes.ROUTE_KEY
PRODUCT_KEY = "console:product"


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


def _on_product_change() -> None:
    """segmented_control 回调：只写路由，重跑交给 Streamlit。"""
    product = st.session_state.get(PRODUCT_KEY)
    if product in routes.PRODUCTS:
        routes.set_route(routes.Route(product=product))


def _product_bar(route: routes.Route) -> None:
    """品牌 + 一个产品级 segmented_control；整条吸顶，值恒由 route 派生。

    为什么不是三个按钮：按钮无法表达"当前在哪一档"，也没有 tab 的键盘语义；
    吸顶容器解决"滚下去就点不到"，route→widget 的单向同步解决"深链被旧值盖住"。
    """
    with st.container(key="ah-nav"):
        brand, tabs, status = st.columns([2.0, 3.4, 2.0], vertical_alignment="center")
        brand.markdown(
            '<div class="ah-brand"><span class="ah-brand-mark">A</span>'
            "<span><b>Agent Harness</b><small>Runtime &amp; Eval</small></span></div>",
            unsafe_allow_html=True,
        )
        sync_widget(PRODUCT_KEY, route.product)
        with tabs:
            st.segmented_control(
                "产品",
                list(routes.PRODUCTS),
                key=PRODUCT_KEY,
                format_func=lambda value: routes.PRODUCT_LABELS.get(value, value),
                on_change=_on_product_change,
                label_visibility="collapsed",
            )
        status.markdown(
            '<div class="ah-nav-status"><span><i></i>本地控制台</span></div>',
            unsafe_allow_html=True,
        )
    if route.unknown_product:
        st.caption(f"未知的产品：`{route.unknown_product}`，已回到对话。")


def run() -> None:
    route = current_route()
    # 入口列表已经移到对话页内容左列，三个产品都不再需要 sidebar：
    # 统一收起，切换产品时不会因为侧栏开合让整条导航横移。
    st.set_page_config(
        page_title="Agent Harness 控制台",
        page_icon="🛠",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    inject_css()
    _product_bar(route)
    if route.product == "build":
        build.render(route)
    elif route.product == "quality":
        quality.render(route)
    else:
        chat.render(route)
