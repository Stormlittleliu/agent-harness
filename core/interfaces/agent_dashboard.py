# -*- coding: utf-8 -*-
"""Agent 可视化控制台：页面骨架、场景切换与视图分发。

具体视图拆在 ``core.interfaces.dashboard``：
- overview：总览页顶部 KPI 行；
- architecture：工具体系、中间件顺序、LangGraph 工作流；
- task：输入任务，查看工具调用、token、时延与 trace；
- tests：运行 cases.jsonl，复用 core.quality.agent_eval 的评分逻辑；
- benchmarks：BFCL / RGB / MultiHop / τ² 的已有报告；
- optimization：最小优化循环的 iteration 结果与 report.md；
- catalog：统一 benchmark 样例集（manifest + catalog.jsonl）；
- history：浏览 outputs/ 下已有的评测报告、Markdown 与 trace。
"""
from __future__ import annotations

import os

import streamlit as st

from core.interfaces.dashboard.architecture import render_architecture
from core.interfaces.dashboard.benchmarks import render_benchmarks
from core.interfaces.dashboard.catalog import render_catalog
from core.interfaces.dashboard.common import load_agent
from core.interfaces.dashboard.cost import render_cost
from core.interfaces.dashboard.editor import render_editor
from core.interfaces.dashboard.evaluation import render_evaluation
from core.interfaces.dashboard.history import render_history
from core.interfaces.dashboard.layout import inject_css
from core.interfaces.dashboard.optimization import render_optimization
from core.interfaces.dashboard.overview import render_overview
from core.interfaces.dashboard.review import render_review
from core.interfaces.dashboard.runtime import render_runtime
from core.interfaces.dashboard.task import render_task
from core.interfaces.dashboard.tests import render_tests
from core.scenarios import library

BASE_VIEWS = [
    "architecture",
    "editor",
    "task",
    "tests",
    "evaluation",
    "review",
    "optimization",
    "catalog",
]


VIEW_LABELS = {
    "architecture": "🧠 Agent 架构",
    "editor": "🎛 场景编辑",
    "task": "🔧 任务执行",
    "tests": "🧪 测试用例",
    "evaluation": "📈 评测",
    "review": "🧾 复核",
    "benchmarks": "📊 公开基准",
    "optimization": "🔁 优化循环",
    "catalog": "🗂 Benchmark 目录",
    "cost": "💸 成本 / 时延",
    "history": "📁 评测记录",
    "runtime": "🖥 运行窗口",
}
AGENT_VIEWS = {"architecture", "task", "tests", "runtime"}
CUSTOM_VIEWS: dict = {}


def _nav_label(view: str) -> str:
    if view == "overview":
        return "🏠 总览"
    return VIEW_LABELS.get(view, view)


def _clear_scenario_state() -> None:
    """切换场景时清掉上一个场景的任务、测试与筛选状态。"""
    for key in (
        "last_task",
        "test_results",
        "test_summary",
        "test_judge",
        "task_query",
        "tests-selected-case",
        "tests-detail-mode",
        "tests-view-mode",
        "tests-category-filter",
        "tests-status-filter",
        "tests-tool-filter",
        "tests-search",
        "tests-run-ids",
        "tests-use-judge",
        "tests-object-tool",
        "tests-object-case",
        "tests-filter-signature",
        "tests-table-nonce",
        "task-detail-mode",
        "architecture-object-search",
        "architecture-tool-select",
        "architecture-object-select",
        "object-middleware-select",
        "editor-current",
        "editor-draft",
        "editor-errors",
        "editor-notice",
        "editor-scenario",
        "runtime-status-filter",
        "runtime-selected-task",
        "runtime-log-select",
        "cost-run-breakdown",
        "benchmarks-mode",
        "benchmarks-tau2-selected",
        "bfcl-kind",
        "bfcl-status",
        "public-bench",
        "optimization-mode",
        "opt-iteration",
        "opt-ab-a",
        "opt-ab-b",
        "opt-ab-case",
        "opt-ab-scope",
        "opt-case-search",
        "opt-dataset",
        "opt-families",
        "opt-failures",
        "opt-passed",
        "cat-search",
        "cat-sources",
        "cat-categories",
        "cat-buckets",
        "cat-task-types",
        "catalog-selected-task",
        "catalog-filter-signature",
        "catalog-table-nonce",
        "history-type",
        "history-search",
        "history-selected-file",
        "history-filter-signature",
        "history-table-nonce",
        "_pending_nav",
        "_object_focus",
    ):
        st.session_state.pop(key, None)


def _render_view(
    view: str,
    agent,
    agent_error: str | None,
    examples: list[str],
    scenario_name: str,
) -> None:
    if (view in AGENT_VIEWS or view in CUSTOM_VIEWS) and agent is None:
        detail = f" 原因：{agent_error}" if agent_error else ""
        st.error(f"Agent 加载失败，无法显示该视图。{detail}")
        return
    if view == "architecture":
        render_architecture(agent)
    elif view == "editor":
        render_editor()
    elif view == "task":
        render_task(agent, examples)
    elif view == "tests":
        render_tests(agent)
    elif view == "runtime":
        render_runtime(agent)
    elif view == "evaluation":
        render_evaluation(scenario_name)
    elif view == "review":
        render_review()
    elif view == "benchmarks":
        render_benchmarks()
    elif view == "optimization":
        render_optimization()
    elif view == "catalog":
        render_catalog()
    elif view == "cost":
        render_cost()
    elif view == "history":
        render_history()
    elif view in CUSTOM_VIEWS:
        CUSTOM_VIEWS[view](agent)
    else:
        st.info(f"未注册的视图：{view}")


def run() -> None:
    st.set_page_config(page_title="Agent 控制台", page_icon="🛠", layout="wide")
    inject_css()
    entries = library.entries()
    names = [item.name for item in entries]
    # 可选：`AH_DASHBOARD_SCENARIO` / `AH_DASHBOARD_VIEW` 让演示、截图和外部链接
    # 从一个指定场景/页面启动；只影响首次渲染，之后仍由侧边栏控制。
    env_scenario = os.getenv("AH_DASHBOARD_SCENARIO", "").strip()
    env_view = os.getenv("AH_DASHBOARD_VIEW", "").strip()
    start_scenario = env_scenario if env_scenario in names else library.default_name()

    # 场景选择放在侧边栏最上面：它是"一等对象"，页面只是场景的一个动作。
    with st.sidebar:
        st.header("场景")
        scenario_name = st.selectbox(
            "场景",
            names,
            index=names.index(start_scenario) if start_scenario in names else 0,
            format_func=library.label,
            key="dashboard-scenario-name",
            help="场景库里的一项；总路由也是一种场景。换场景会保留当前页面。",
        )

    entry = library.entry(scenario_name)
    views = [view for view in BASE_VIEWS if view in VIEW_LABELS]
    if entry is not None and entry.supports_runtime and "runtime" in VIEW_LABELS:
        views.insert(views.index("tests") + 1, "runtime") if "tests" in views else views.append("runtime")
    views = [view for view in views if view in VIEW_LABELS or view in CUSTOM_VIEWS] or list(DEFAULT_VIEWS)
    examples = list(entry.examples) if entry is not None else []

    # 切换场景时清掉上一个场景的任务、测试与筛选状态，避免串台
    if st.session_state.get("dashboard_scenario") != scenario_name:
        _clear_scenario_state()
        st.session_state["dashboard_scenario"] = scenario_name

    top_left, top_badge = st.columns([6.2, 2.4], gap="small", vertical_alignment="bottom")
    with top_left:
        st.markdown("### 🛠 Agent Harness 控制台")
        st.caption("先在左侧选场景，再看它：结构 / 任务 / 用例 / 评测。只渲染当前视图，不触发模型调用，除非主动运行。")
    with top_badge:
        if entry is not None:
            st.caption(f"{entry.title} · `{entry.badge}` · 用例 {entry.cases} 条")

    with st.sidebar:
        st.header("页面")
        nav_options = ["overview"] + views
        # 快捷入口按钮通过 on_click 写入 _pending_nav；在 radio 实例化前应用。
        pending = st.session_state.pop("_pending_nav", None)
        if pending in nav_options:
            st.session_state["dashboard-nav"] = pending
            st.session_state["_desired_view"] = pending
        if "dashboard-nav" not in st.session_state and env_view in nav_options:
            st.session_state["dashboard-nav"] = env_view
            st.session_state["_desired_view"] = env_view

        # 切换场景时 Streamlit 可能先把 dashboard-nav 重置为默认值。
        # 用独立的 _desired_view 记住用户最后停留的页面：
        # - 新场景支持该页：直接恢复；
        # - 新场景不支持（例如 runtime）：仍保留为 sticky 选项，
        #   由视图自己渲染空状态，而不是跳回总览。
        current_nav = st.session_state.get("dashboard-nav")
        sticky_view = st.session_state.get("_desired_view")
        if current_nav not in nav_options:
            if sticky_view in nav_options:
                st.session_state["dashboard-nav"] = sticky_view
            elif sticky_view in VIEW_LABELS or sticky_view in CUSTOM_VIEWS:
                nav_options.append(sticky_view)
                st.session_state["dashboard-nav"] = sticky_view
            else:
                st.session_state.pop("dashboard-nav", None)
        nav = st.radio(
            "页面",
            nav_options,
            format_func=_nav_label,
            key="dashboard-nav",
            help="只渲染当前页面；切换子场景时保留当前页，不支持的页会显示空状态。",
        )
        st.session_state["_desired_view"] = nav

        st.divider()
        st.markdown(f"**当前场景**：{library.label(scenario_name)}")
        st.caption(f"{len(views)} 个页面 · 切换场景保持当前页；数据视图只读已有文件，不触发模型调用。")
        st.caption("编辑：场景 · 分析：架构 / 任务 / 用例 · 评测：报告 / 成本 / 基准 / 记录")

    # 总览不加载 Agent：首屏只读 KPI / 报告元数据，避免 RAG/Chroma 初始化拖慢。
    needs_agent = nav in AGENT_VIEWS or nav in CUSTOM_VIEWS
    agent = None
    agent_error = None
    if needs_agent:
        try:
            with st.spinner("正在加载 Agent 与知识库..."):
                agent = load_agent(scenario_name)
        except Exception as exc:  # noqa: BLE001 - 数据视图仍应可用
            agent_error = f"{type(exc).__name__}: {exc}"

    page_label = _nav_label(nav)
    description = f" — {agent.scenario.description}" if agent is not None else ""
    st.caption(f"当前场景：**{library.label(scenario_name)}** · 当前页面：**{page_label}**{description}")

    if nav == "overview":
        render_overview(scenario_name, views, VIEW_LABELS)
    else:
        _render_view(nav, agent, agent_error, examples, scenario_name)
