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
from core.interfaces.dashboard.layout import page_header
from core.interfaces.dashboard.optimization import render_optimization
from core.interfaces.dashboard.review import render_review
from core.interfaces.dashboard.tests import render_tests
from core.scenarios import library

VIEWS = ("评测", "复核", "优化", "自检", "数据集", "基准", "成本", "记录")


def render(route: routes.Route) -> None:
    names = library.names()
    page_header(
        "质量",
        "评测与复核：这一页的对象是「一次运行」，场景只是维度。"
        "数据集的结构化改造还没做，先把已有视图接过来。",
        meta=f"{len(names)} 个场景可选" if names else "还没有场景",
    )
    if not names:
        st.info("场景库是空的。")
        return

    scenario = st.selectbox(
        "场景",
        names,
        index=names.index(library.default_name()),
        format_func=library.label,
        key="quality:scenario",
        help="只影响质量页的评测对象；不会改变对话或构建里正在用的场景。",
    )
    view = st.radio("视图", VIEWS, horizontal=True, key="quality:view")

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
    else:
        render_history()
