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

import streamlit as st

from core.interfaces.dashboard.architecture import render_architecture
from core.interfaces.dashboard.benchmarks import render_benchmarks
from core.interfaces.dashboard.catalog import render_catalog
from core.interfaces.dashboard.common import load_agent
from core.interfaces.dashboard.history import render_history
from core.interfaces.dashboard.optimization import render_optimization
from core.interfaces.dashboard.overview import render_overview_kpis
from core.interfaces.dashboard.runtime import render_runtime
from core.interfaces.dashboard.task import render_task
from core.interfaces.dashboard.tests import render_tests
from core.scenarios.registry import list_scenarios

DEFAULT_SCENARIO = "general"
SCENARIO_LABELS = {
    "coding_demo": "coding_demo · 编码运行时",
    "general": "general · 白板",
    "mcp_demo": "mcp_demo · Memory + Fetch",
    "robot_vacuum": "robot_vacuum · 扫地机器人",
}
DASHBOARD_PRESETS = {
    "general": {
        "views": [
            "architecture",
            "task",
            "tests",
            "benchmarks",
            "optimization",
            "catalog",
            "history",
        ],
        "examples": [
            "你好，请用一句话介绍你自己。",
            "1+1 等于几？",
            "把“今天天气很好”翻译成英文。",
        ],
    },
    "robot_vacuum": {
        "views": [
            "architecture",
            "task",
            "tests",
            "benchmarks",
            "optimization",
            "catalog",
            "history",
        ],
        "examples": [
            "小户型适合哪些扫地机器人？",
            "给我生成我的使用报告",
            "今天天气怎么样",
        ],
    },
    "mcp_demo": {
        "views": [
            "architecture",
            "task",
            "tests",
            "benchmarks",
            "optimization",
            "catalog",
            "history",
        ],
        "examples": [
            "请记住：我喜欢小户型，家里有猫。",
            "根据你记住的偏好，我喜欢什么户型？",
            "读取 https://example.com 并告诉我页面标题。",
        ],
    },
    "coding_demo": {
        "views": [
            "architecture",
            "task",
            "tests",
            "runtime",
            "benchmarks",
            "optimization",
            "catalog",
            "history",
        ],
        "examples": [
            "读取 README.md，并告诉我这个工作区叫什么名字。",
            "在工作区运行 echo hello，并告诉我输出。",
            "创建一个任务：检查项目结构。",
        ],
    },
}
DEFAULT_VIEWS = [
    "architecture",
    "task",
    "tests",
    "benchmarks",
    "optimization",
    "catalog",
    "history",
]
VIEW_LABELS = {
    "architecture": "🧠 Agent 架构",
    "task": "🔧 任务执行",
    "tests": "🧪 测试用例",
    "benchmarks": "📊 公开基准",
    "optimization": "🔁 优化循环",
    "catalog": "🗂 Benchmark 目录",
    "history": "📁 评测记录",
    "runtime": "🖥 运行窗口",
}
AGENT_VIEWS = {"architecture", "task", "tests", "runtime"}
CUSTOM_VIEWS: dict = {}


def _nav_label(view: str) -> str:
    if view == "overview":
        return "🏠 总览（全部标签）"
    return VIEW_LABELS.get(view, view)


def _render_view(view: str, agent, agent_error: str | None, examples: list[str]) -> None:
    if (view in AGENT_VIEWS or view in CUSTOM_VIEWS) and agent is None:
        detail = f" 原因：{agent_error}" if agent_error else ""
        st.error(f"Agent 加载失败，无法显示该视图。{detail}")
        return
    if view == "architecture":
        render_architecture(agent)
    elif view == "task":
        render_task(agent, examples)
    elif view == "tests":
        render_tests(agent)
    elif view == "runtime":
        render_runtime(agent)
    elif view == "benchmarks":
        render_benchmarks()
    elif view == "optimization":
        render_optimization()
    elif view == "catalog":
        render_catalog()
    elif view == "history":
        render_history()
    elif view in CUSTOM_VIEWS:
        CUSTOM_VIEWS[view](agent)
    else:
        st.info(f"未注册的视图：{view}")


def run() -> None:
    st.set_page_config(page_title="Agent 控制台", page_icon="🛠", layout="wide")
    st.title("🛠 Agent Harness 控制台")
    st.caption(
        "架构 / 任务执行 / 测试用例 / 公开基准 / 优化循环 / Benchmark 目录 / 评测记录"
    )

    names = list_scenarios()
    default_index = names.index(DEFAULT_SCENARIO) if DEFAULT_SCENARIO in names else 0

    with st.sidebar:
        st.header("导航")
        scenario_name = st.selectbox(
            "场景 / 前端预设",
            names,
            index=default_index,
            format_func=lambda name: SCENARIO_LABELS.get(name, name),
            key="dashboard-scenario",
            help="切换场景会重新加载对应的 Agent；数据视图不依赖场景。",
        )
        preset = DASHBOARD_PRESETS.get(scenario_name, {})
        views = [
            view
            for view in preset.get("views", DEFAULT_VIEWS)
            if view in VIEW_LABELS or view in CUSTOM_VIEWS
        ]
        if not views:
            views = list(DEFAULT_VIEWS)
        examples = preset.get("examples", [])

        nav_options = ["overview"] + views
        if st.session_state.get("dashboard-nav") not in nav_options:
            st.session_state.pop("dashboard-nav", None)
        nav = st.radio(
            "页面",
            nav_options,
            format_func=_nav_label,
            key="dashboard-nav",
            help="总览模式保留顶部标签页；选择一个页面可直接进入单页视图。",
        )

        st.divider()
        scenario_label = SCENARIO_LABELS.get(scenario_name, scenario_name)
        st.markdown(f"**当前场景**：{scenario_label}")
        st.caption(f"{len(views)} 个视图 · 数据视图只读已有文件，不触发模型调用。")

    # 切换场景时清掉上一个场景的任务与测试结果，避免串台
    if st.session_state.get("dashboard_scenario") != scenario_name:
        for key in (
            "last_task",
            "test_results",
            "test_summary",
            "test_judge",
            "task_query",
        ):
            st.session_state.pop(key, None)
        st.session_state["dashboard_scenario"] = scenario_name

    needs_agent = nav == "overview" or nav in AGENT_VIEWS or nav in CUSTOM_VIEWS
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
    st.caption(f"当前场景：**{scenario_label}** · 当前页面：**{page_label}**{description}")

    if nav == "overview":
        render_overview_kpis()
        tabs = st.tabs([VIEW_LABELS.get(view, view) for view in views])
        for tab, view in zip(tabs, views):
            with tab:
                _render_view(view, agent, agent_error, examples)
    else:
        st.subheader(_nav_label(nav))
        _render_view(nav, agent, agent_error, examples)
