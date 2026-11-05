# -*- coding: utf-8 -*-
"""质量端：评测 / 复核 / 优化 / 自检 / 数据集 / 基准 / 成本 / 记录。

这一块是"一次运行"的工作台，所以它的上下文是**运行**，不是场景；场景只是
评测的一个维度（顶部选择器只影响这一页，不碰对话与构建的状态）。

当前阶段先把原控制台的视图整体搬进来（它们已经能读报告、跑用例），
数据集的结构化改造（增删改、版本、导入导出）排在下一阶段。
"""
from __future__ import annotations

import streamlit as st

from core.interfaces.console import routes
from core.interfaces.dashboard.benchmarks import render_benchmarks
from core.interfaces.dashboard.catalog import render_catalog
from core.interfaces.dashboard.common import load_agent
from core.interfaces.dashboard.cost import render_cost
from core.interfaces.dashboard.evaluation import render_evaluation
from core.interfaces.dashboard.history import render_history
from core.interfaces.dashboard.layout import page_header, sync_widget
from core.interfaces.dashboard.optimization import render_optimization
from core.interfaces.dashboard.patterns import render_patterns
from core.interfaces.dashboard.review import render_review
from core.interfaces.dashboard.tests import render_tests
from core.scenarios import library

# 9 个视图不再横排成一排 radio；按"跑一次 / 看资产 / 查记录"分组。
VIEW_GROUPS = {
    "跑一次": ("评测", "复核", "优化", "自检"),
    "看资产": ("数据集", "基准", "成本", "范式"),
    "查记录": ("记录",),
}
GROUP_KEY = "quality:group"
VIEW_KEY = "quality:view"


def render(route: routes.Route) -> None:
    names = library.names()
    page_header(
        "质量",
        "以一次运行作为工作对象：先跑评测，再看资产，最后查记录；场景只是维度。",
        meta=f"{len(names)} 个场景可选" if names else None,
    )
    if not names:
        st.info("场景库是空的。")
        return

    with st.container(border=True, key="quality-context"):
        top = st.columns([2.15, 4.15], gap="large", vertical_alignment="bottom")
        with top[0]:
            scenario = st.selectbox(
                "当前场景",
                names,
                index=names.index(library.default_name()),
                format_func=library.label,
                key="quality:scenario",
                help="只影响质量页的评测对象；不会改变对话或构建里正在用的场景。",
            )
        with top[1]:
            st.markdown('<div class="ah-quality-view">视图分组</div>', unsafe_allow_html=True)
            group = st.segmented_control(
                "分组",
                list(VIEW_GROUPS),
                key=GROUP_KEY,
                label_visibility="collapsed",
            )
        if group not in VIEW_GROUPS:
            group = next(iter(VIEW_GROUPS))
        views = VIEW_GROUPS[group]
        if st.session_state.get(VIEW_KEY) not in views:
            sync_widget(VIEW_KEY, views[0])
        st.markdown('<div class="ah-quality-view">当前视图</div>', unsafe_allow_html=True)
        view = st.segmented_control(
            "视图",
            list(views),
            key=VIEW_KEY,
            label_visibility="collapsed",
        )
        if view not in views:
            view = views[0]

    if view == "评测":
        render_evaluation(scenario)
    elif view == "复核":
        render_review()
    elif view == "优化":
        render_optimization()
    elif view == "自检":
        with st.spinner("正在加载 Agent 与知识库…"):
            agent = load_agent(scenario)
        render_tests(agent)
    elif view == "数据集":
        render_catalog()
    elif view == "基准":
        render_benchmarks()
    elif view == "成本":
        render_cost()
    elif view == "范式":
        render_patterns(scenario)
    else:
        render_history()
