# -*- coding: utf-8 -*-
"""架构视图：场景、工具、中间件与 LangGraph 工作流。"""
from __future__ import annotations

import streamlit as st

from core.agent.framework import FrameworkAgent
from core.interfaces.dashboard.common import load_agent

MIDDLEWARE_DESC = {
    "ToolPermissionMiddleware": "工具权限：按 allow/deny 拦截，拒绝的工具不会进入后续链路",
    "MonitorToolMiddleware": "工具日志：记录工具名、参数与调用结果",
    "ValidateToolArgsMiddleware": "参数校验：拦截非法业务参数并回注错误",
    "IntentRouterMiddleware": "意图路由：命中关键词时走报告流程",
    "LogBeforeModelMiddleware": "模型日志：调用前记录上下文消息数",
    "LimitStepsMiddleware": "步数上限：限制 ReAct 循环次数",
    "ReportPromptSwitchMiddleware": "提示词切换：报告意图使用专用 prompt",
    "TodoListMiddleware": "任务规划：复杂任务自动维护 todo",
    "SummarizationMiddleware": "上下文压缩：历史过长时先摘要",
    "PIIMiddleware": "敏感信息脱敏：email / credit_card / ip",
    "HumanInTheLoopMiddleware": "高风险审批：reset_device 需要人工确认",
    "ToolTimeoutMiddleware": "工具超时：按工具配置执行时限，超时中断",
    "ToolErrorMiddleware": "异常回注：工具错误转成中文消息交给模型",
    "ToolRetryMiddleware": "工具重试：失败后重试 1 次",
    "ToolCallLimitMiddleware": "调用上限：限制单次 run 的工具调用次数",
    "TokenBudgetMiddleware": "Token 预算：超限时在下一次模型调用前截断",
    "ModelRetryMiddleware": "模型重试：失败后重试 1 次",
}


@st.cache_resource(show_spinner=False)
def _graphs(scenario_name: str) -> dict:
    scenario = load_agent(scenario_name).scenario
    if not scenario.workflow_factory:
        return {}
    return scenario.workflow_factory(scenario)


def _to_dot(graph) -> str:
    """把 LangGraph 的边转成 Graphviz DOT，Streamlit 可直接渲染。"""
    labels = {"__start__": "START", "__end__": "END"}
    lines = [
        "digraph G {",
        "rankdir=LR;",
        'node [shape=box, style="rounded,filled", fillcolor="#EEF4FF", fontsize=11];',
    ]
    nodes = set()
    for edge in graph.edges:
        source = labels.get(edge.source, edge.source)
        target = labels.get(edge.target, edge.target)
        nodes.update({source, target})
        style = " [style=dashed]" if getattr(edge, "conditional", False) else ""
        lines.append(f'  "{source}" -> "{target}"{style};')
    for node in nodes:
        if node in {"START", "END"}:
            lines.append(f'  "{node}" [shape=oval, fillcolor="#E8F5E9"];')
    lines.append("}")
    return "\n".join(lines)


def render_architecture(agent: FrameworkAgent) -> None:
    scenario = agent.scenario
    st.subheader("场景")
    st.write(f"**{scenario.name}** — {scenario.description}")

    model_name = getattr(scenario.model, "model_name", None) or "unknown"
    cols = st.columns(5)
    cols[0].metric("工具", len(scenario.tools))
    cols[1].metric("中间件", len(agent.middleware))
    cols[2].metric("Token 预算", f"{scenario.token_budget:,}" if scenario.token_budget else "不限")
    cols[3].metric("工具调用上限", scenario.tool_call_limit or "不限")
    cols[4].metric("模型", model_name)

    st.subheader("工具")
    if not scenario.tools:
        st.info("当前场景没有业务工具；框架内置的 `write_todos` 不在此表中。")
    else:
        risk = (scenario.tool_policy or {}).get("risk_levels", {})
        st.dataframe(
            [
                {
                    "工具": tool.name,
                    "说明": (tool.description or "").split("\n")[0][:60],
                    "风险": risk.get(tool.name, "-"),
                    "人工审批": "✅" if tool.name in scenario.high_risk_tools else "",
                }
                for tool in scenario.tools
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("中间件执行顺序")
    sequence: list[list] = []
    for middleware in agent.middleware:
        name = type(middleware).__name__
        if sequence and sequence[-1][0] == name:
            sequence[-1][1] += 1
        else:
            sequence.append([name, 1])
    for index, (name, count) in enumerate(sequence, 1):
        suffix = f" ×{count}" if count > 1 else ""
        st.markdown(f"`{index:02d}` **{name}{suffix}** — {MIDDLEWARE_DESC.get(name, '')}")

    st.subheader("LangGraph 工作流")
    try:
        graphs = _graphs(scenario.name)
    except Exception as exc:  # noqa: BLE001 - 工作流构建失败不应打断整个页面
        st.error(f"工作流加载失败：{type(exc).__name__}: {exc}")
        return
    if not graphs:
        st.info("当前场景没有注册工作流。")
        return
    for name, compiled in graphs.items():
        st.markdown(f"**{name}**")
        st.graphviz_chart(_to_dot(compiled.get_graph()), use_container_width=True)
