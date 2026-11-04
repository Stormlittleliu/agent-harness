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
from core.scenarios.registry import list_scenarios

DEFAULT_SCENARIO = "router"
ENTRY_ROUTER = "router · 总路由（自动分流）"
ENTRY_CHILD = "子场景 · 直接进入"
SCENARIO_LABELS = {
    "coding_demo": "coding_demo · 编码运行时",
    "general": "general · 白板",
    "mcp_demo": "mcp_demo · Memory + Fetch",
    "research_assistant": "research_assistant · 研究调研",
    "robot_vacuum": "robot_vacuum · 扫地机器人",
    "router": "router · 总路由",
    "structured_demo": "structured_demo · 结构化输出",
    "workspace_assistant": "workspace_assistant · 办公学习",
}
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
CODING_VIEWS = [
    "architecture",
    "editor",
    "task",
    "tests",
    "runtime",
    "evaluation",
    "review",
    "optimization",
    "catalog",
]

DASHBOARD_PRESETS = {
    "general": {
        "views": BASE_VIEWS,
        "examples": [
            "你好，请用一句话介绍你自己。",
            "1+1 等于几？",
            "把“今天天气很好”翻译成英文。",
        ],
    },
    "robot_vacuum": {
        "views": BASE_VIEWS,
        "examples": [
            "小户型适合哪些扫地机器人？",
            "给我生成我的使用报告",
            "今天天气怎么样",
        ],
    },
    "mcp_demo": {
        "views": BASE_VIEWS,
        "examples": [
            "请记住：我喜欢小户型，家里有猫。",
            "根据你记住的偏好，我喜欢什么户型？",
            "读取 https://example.com 并告诉我页面标题。",
        ],
    },
    "coding_demo": {
        "views": CODING_VIEWS,
        "examples": [
            "读取 README.md，并告诉我这个工作区叫什么名字。",
            "在工作区运行 echo hello，并告诉我输出。",
            "创建一个任务：检查项目结构。",
        ],
    },
    "structured_demo": {
        "views": BASE_VIEWS,
        "examples": [
            "材料：接口联调延后到周五；测试环境不稳定。请生成结构化报告。",
            "材料：Transformer 由多头注意力和前馈网络组成。请生成结构化报告。",
            "Material: X1 supports 5000Pa suction and 180 minutes runtime. Please generate a structured report in Chinese.",
        ],
    },
    "workspace_assistant": {
        "views": BASE_VIEWS,
        "examples": [
            "根据笔记，Agent 评测应该关注哪些指标？",
            "Summarize the product brief in Chinese.",
            "把“Agent 评测要看 outcome”写成一条笔记。",
            "请记住：我喜欢简洁的回答，并用要点列出。",
        ],
    },
    "research_assistant": {
        "views": BASE_VIEWS,
        "examples": [
            "列出当前有哪些研究资料。",
            "对比三份资料对 Agent 评测的主要观点，并给出来源。",
            "根据三份资料写一份简短的对比报告并保存。",
        ],
    },
    "router": {
        "views": BASE_VIEWS,
        "examples": [
            "帮我写一个输出 99 乘法表的 Python 脚本并运行验证。",
            "根据笔记帮我整理一份 Agent 评测的学习计划。",
            "扫地机器人回充失败怎么办？",
            "对比三份资料，告诉我它们对 Agent 评测的主要差异。",
        ],
    },
}
DEFAULT_VIEWS = BASE_VIEWS
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


def _entry_label(value: str) -> str:
    return "总路由" if value == ENTRY_ROUTER else "子场景"


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
    names = list_scenarios()
    # 可选：`AH_DASHBOARD_SCENARIO` / `AH_DASHBOARD_VIEW` 让演示、截图和外部链接
    # 从一个指定页面启动；只在首次 session 生效，之后仍由页面右上角控制。
    env_scenario = os.getenv("AH_DASHBOARD_SCENARIO", "").strip()
    env_view = os.getenv("AH_DASHBOARD_VIEW", "").strip()
    child_names = [name for name in names if name != "router"]
    start_child = env_scenario if env_scenario in child_names else (
        "workspace_assistant" if "workspace_assistant" in child_names else child_names[0]
    )
    if env_scenario and "dashboard-entry" not in st.session_state:
        st.session_state["dashboard-entry"] = (
            ENTRY_ROUTER if env_scenario == "router" else ENTRY_CHILD
        )
    if env_scenario in child_names and "dashboard-child-scenario" not in st.session_state:
        st.session_state["dashboard-child-scenario"] = env_scenario

    # 入口模式 / 子场景放在主内容右上角，跟随页面滚动，不固定在侧边栏。
    top_left, top_entry, top_child = st.columns(
        [6.2, 1.8, 2.4], gap="small", vertical_alignment="bottom"
    )
    with top_left:
        st.markdown("### 🛠 Agent Harness 控制台")
        st.caption("场景 → 任务 / 用例 / 评测；只渲染当前视图，不触发模型调用，除非主动运行。")
    with top_entry:
        entry = st.selectbox(
            "入口模式",
            [ENTRY_ROUTER, ENTRY_CHILD],
            format_func=_entry_label,
            key="dashboard-entry",
            label_visibility="collapsed",
            help="总路由：由 router 自动判断目标场景；子场景：直接进入某个场景，不经过 router。",
        )
    with top_child:
        if entry == ENTRY_CHILD:
            scenario_name = st.selectbox(
                "子场景",
                child_names,
                index=child_names.index(start_child),
                format_func=lambda name: SCENARIO_LABELS.get(name, name),
                key="dashboard-child-scenario",
                label_visibility="collapsed",
                help="直接进入子场景，不经过 router；工具和 checkpoint 仍按该场景隔离。",
            )
        else:
            scenario_name = "router"
            st.caption("总路由 · 自动分流到 workspace / coding / robot / research")

    preset = DASHBOARD_PRESETS.get(scenario_name, {})
    views = [
        view
        for view in preset.get("views", DEFAULT_VIEWS)
        if view in VIEW_LABELS or view in CUSTOM_VIEWS
    ]
    if not views:
        views = list(DEFAULT_VIEWS)
    examples = preset.get("examples", [])
    scenario_label = SCENARIO_LABELS.get(scenario_name, scenario_name)

    # 切换场景时清掉上一个场景的任务、测试与筛选状态，避免串台
    if st.session_state.get("dashboard_scenario") != scenario_name:
        _clear_scenario_state()
        st.session_state["dashboard_scenario"] = scenario_name

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
        st.markdown(f"**当前场景**：{scenario_label}")
        st.caption(f"{len(views)} 个视图 · 切换场景保持当前页；数据视图只读已有文件，不触发模型调用。")
        st.caption("工作台：架构 / 任务 / 用例 · 评测：场景报告 / 成本 / 基准 / 记录 · 数据：目录")

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
    st.caption(f"当前场景：**{scenario_label}** · 当前页面：**{page_label}**{description}")

    if nav == "overview":
        render_overview(scenario_name, views, VIEW_LABELS)
    else:
        _render_view(nav, agent, agent_error, examples, scenario_name)
