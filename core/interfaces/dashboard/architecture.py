# -*- coding: utf-8 -*-
"""架构视图：场景、工具、中间件、工作流与对象源码。

左栏是“系统有什么”，右栏是“工作流怎么走”；每个工具/中间件都带
`module:line`，可以从这里跳到测试用例，也可以反查对象实现。
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from core.agent.framework import FrameworkAgent
from core.interfaces.dashboard.common import load_agent, load_cases_cached
from core.interfaces.dashboard.layout import (
    Kpi,
    compact_table,
    kpi_row,
    master_detail,
    navigate,
    page_header,
    section,
)
from core.interfaces.dashboard.objects import build_object_index, case_tool_index, render_object_card

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
    "ModelFallbackMiddleware": "模型回退：主模型失败时切换备用模型",
}

# 只记录、不改变执行结果的中间件：合并成一行，不展开。
LOGGING_MIDDLEWARE = {"MonitorToolMiddleware", "LogBeforeModelMiddleware"}


def _safe_value(value, depth: int = 0):
    """把中间件配置转成可展示的简单值，避免把对象/函数塞进 JSON。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if depth >= 1:
        return type(value).__name__
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(item, depth + 1) for item in list(value)[:12]]
    if isinstance(value, dict):
        return {
            str(key): _safe_value(item, depth + 1)
            for key, item in list(value.items())[:12]
        }
    return type(value).__name__


def _middleware_config(mw) -> dict:
    """只提取会改变执行/上下文的关键配置，不 dump 整个对象。"""
    cls = type(mw).__name__
    if cls == "ToolPermissionMiddleware":
        return {
            "default": getattr(mw, "default", None),
            "allow": sorted(getattr(mw, "allow", set())),
            "deny": sorted(getattr(mw, "deny", set())),
            "risk_levels": getattr(mw, "risk_levels", {}),
        }
    if cls == "ValidateToolArgsMiddleware":
        return {"validators": sorted((getattr(mw, "validators", {}) or {}).keys())}
    if cls == "ToolTimeoutMiddleware":
        return {
            "default_timeout": getattr(mw, "default_timeout", None),
            "overrides": getattr(mw, "overrides", {}),
        }
    if cls == "ToolCallLimitMiddleware":
        return {
            "run_limit": getattr(mw, "run_limit", None),
            "exit_behavior": getattr(mw, "exit_behavior", None),
        }
    if cls == "ToolRetryMiddleware":
        return {
            "max_retries": getattr(mw, "max_retries", None),
            "on_failure": getattr(mw, "on_failure", None),
        }
    if cls == "ModelRetryMiddleware":
        return {"max_retries": getattr(mw, "max_retries", None)}
    if cls == "ModelFallbackMiddleware":
        fallback = getattr(mw, "fallback_model", None)
        return {"fallback_model": type(fallback).__name__ if fallback is not None else None}
    if cls == "SummarizationMiddleware":
        return {
            "trigger": getattr(mw, "trigger", None),
            "keep": getattr(mw, "keep", None),
        }
    if cls == "PIIMiddleware":
        return {
            "pii_type": getattr(mw, "pii_type", None),
            "strategy": getattr(mw, "strategy", None),
            "apply_to_input": getattr(mw, "apply_to_input", None),
            "apply_to_output": getattr(mw, "apply_to_output", None),
            "apply_to_tool_results": getattr(mw, "apply_to_tool_results", None),
        }
    if cls == "HumanInTheLoopMiddleware":
        return {"interrupt_on": getattr(mw, "interrupt_on", None)}
    if cls == "IntentRouterMiddleware":
        return {"report_keywords": getattr(mw, "report_keywords", [])}
    if cls == "ReportPromptSwitchMiddleware":
        return {"prompts_path": str(getattr(mw, "prompts_path", ""))}
    if cls == "LimitStepsMiddleware":
        return {"max_model_calls": getattr(mw, "max_model_calls", None)}
    if cls == "PlanningPolicyMiddleware":
        policy = getattr(mw, "policy", None)
        rules = getattr(policy, "rules", ())
        return {
            "rules": [
                {
                    "tool": rule.tool,
                    "strong": list(rule.strong_keywords),
                    "keywords": list(rule.keywords),
                }
                for rule in rules
            ],
            "min_score": getattr(policy, "min_score", None),
            "abstain_on_tie": getattr(policy, "abstain_on_tie", None),
        }
    if cls == "TokenBudgetMiddleware":
        return {"budget": "由 Scenario.token_budget 控制"}
    if cls == "TodoListMiddleware":
        return {"planning": "自动维护 write_todos"}
    if cls == "ToolErrorMiddleware":
        return {"error": "异常转成可读 ToolMessage"}
    return {"配置": MIDDLEWARE_DESC.get(cls, "见源码")}


def _render_middleware_chain(agent, index, query: str) -> None:
    """有效中间件按类展开；日志类只占一行。"""
    section("中间件链", "只展开会改变执行/上下文的中间件；日志类合并为一行。")
    groups: dict[str, list[tuple[int, object, object]]] = {}
    logging_entries: list[tuple[int, str, object]] = []
    for order, mw in enumerate(agent.middleware, 1):
        cls = type(mw).__name__
        ref = index.find("middleware", cls)
        if cls in LOGGING_MIDDLEWARE:
            logging_entries.append((order, cls, ref))
            continue
        groups.setdefault(cls, []).append((order, mw, ref))

    if logging_entries:
        names = "、".join(sorted({cls for _, cls, _ in logging_entries}))
        st.caption(f"日志类（只记录，不改变执行）：{names}。")

    rendered = 0
    for cls, items in groups.items():
        desc = MIDDLEWARE_DESC.get(cls, "")
        source = _short_location(items[0][2])
        configs = {
            f"#{order}": _middleware_config(mw)
            for order, mw, _ in items
        }
        haystack = (
            f"{cls} {desc} {source} "
            f"{json.dumps(configs, ensure_ascii=False, default=str)}"
        ).casefold()
        if query and query not in haystack:
            continue
        rendered += 1
        title = f"{items[0][0]:02d}. {cls}"
        if len(items) > 1:
            title += f" ×{len(items)}"
        with st.expander(f"{title} · {desc}", expanded=bool(query)):
            st.caption(f"来源：`{source}`")
            st.code(
                json.dumps(configs, ensure_ascii=False, indent=2, default=str),
                language="json",
            )
    if rendered == 0 and not logging_entries:
        st.caption("当前场景没有会改变执行的中间件。")


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


def _short_location(ref) -> str:
    """表格里只显示 `文件名:行号`，完整路径留给对象卡。"""
    if ref is None:
        return "—"
    if ref.file and ref.lineno:
        return f"{Path(ref.file).name}:{ref.lineno}"
    return ref.location


def _object_options(index) -> tuple[list[str], dict[str, object]]:
    options: list[str] = []
    mapping: dict[str, object] = {}
    for name, ref in index.tools.items():
        label = f"工具 · {name}"
        options.append(label)
        mapping[label] = ref
    for ref in index.middleware:
        label = f"中间件 · {ref.name}"
        options.append(label)
        mapping[label] = ref
    for ref in index.eval_refs.values():
        label = f"评测 · {ref.name}"
        options.append(label)
        mapping[label] = ref
    return options, mapping


def render_architecture(agent: FrameworkAgent) -> None:
    scenario = agent.scenario
    try:
        graphs = _graphs(scenario.name)
    except Exception:  # noqa: BLE001 - 工作流加载失败不应打断架构页
        graphs = {}
    index = build_object_index(agent, graphs=graphs)
    cases, _cases_error = load_cases_cached(scenario.cases_path)
    usage = case_tool_index(cases or [])

    page_header(
        "Agent 架构",
        f"{scenario.name} — {scenario.description}",
        meta=f"工具 {len(scenario.tools)} · 中间件 {len(agent.middleware)} · 用例 {len(cases or [])}",
    )
    kpi_row(
        [
            Kpi("工具", str(len(scenario.tools))),
            Kpi("中间件实例", str(len(agent.middleware))),
            Kpi("用例", str(len(cases or []))),
            Kpi("Token 预算", f"{scenario.token_budget:,}" if scenario.token_budget else "不限"),
        ]
    )

    # 从测试用例页跳转过来时，预填对象搜索（必须在 widget 创建前写入）。
    focus = st.session_state.pop("_object_focus", None)
    if focus:
        st.session_state["architecture-object-search"] = focus

    left, right = master_detail(0.62)
    with left:
        section("工具", "点击“查看相关用例”可反查使用该工具的行为用例。")
        query = st.text_input(
            "搜索工具 / 中间件",
            key="architecture-object-search",
            placeholder="例如 rag_summarize / ToolPermission",
        ).strip().casefold()
        risk = (scenario.tool_policy or {}).get("risk_levels", {})
        tool_rows = []
        for tool in scenario.tools:
            name = str(tool.name)
            ref = index.tools.get(name)
            risk_text = str(risk.get(name, "-"))
            if name in scenario.high_risk_tools:
                risk_text += " · 审批"
            tool_rows.append({
                "工具": name,
                "风险": risk_text,
                "案例": len(usage.get(name, {}).get("expected", [])),
                "源码": _short_location(ref),
            })
        if query:
            tool_rows = [
                row for row in tool_rows
                if query in " ".join(str(row[key]) for key in ("工具", "源码")).casefold()
            ]
        compact_table(
            tool_rows,
            height=280,
            key="architecture-tools-table",
            column_order=["工具", "风险", "案例", "源码"],
            column_config={
                "工具": st.column_config.TextColumn(width="medium"),
                "风险": st.column_config.TextColumn(width="medium"),
                "案例": st.column_config.NumberColumn(width="small"),
                "源码": st.column_config.TextColumn(width="small"),
            },
        )

        _render_middleware_chain(agent, index, query)

        options, mapping = _object_options(index)
        if options:
            with st.expander("查看对象源码", expanded=False):
                selected = st.selectbox("对象", options, key="architecture-object-select")
                ref = mapping.get(selected)
                if ref is not None:
                    render_object_card(ref)
                    if ref.kind == "tool":
                        st.button(
                            "查看相关用例",
                            key="architecture-open-tests",
                            on_click=navigate,
                            args=("tests", ref.name),
                        )

    with right:
        section("工作流", "LangGraph 图；上方是工作流名。")
        if not graphs:
            st.caption("当前场景没有注册工作流。")
        for name, compiled in graphs.items():
            st.markdown(f"**{name}**")
            with st.container(border=True):
                st.graphviz_chart(_to_dot(compiled.get_graph()), use_container_width=True)
            graph = compiled.get_graph()
            edge_rows = [
                {"从": edge.source, "到": edge.target}
                for edge in graph.edges
            ]
            if edge_rows:
                with st.expander("边列表", expanded=False):
                    compact_table(
                        edge_rows,
                        height=160,
                        key=f"architecture-edges-{name}",
                    )

        section("对象索引", "场景 / 工具 / 中间件 / 工作流节点 / 评测函数。")
        project_refs = sum(
            1
            for ref in [
                index.scenario,
                index.agent,
                *index.tools.values(),
                *index.middleware,
                *index.eval_refs.values(),
            ]
            if ref and not ref.external
        )
        external_refs = sum(
            1
            for ref in [*index.middleware, *index.eval_refs.values()]
            if ref.external
        )
        st.caption(f"项目对象 {project_refs} · 框架/第三方对象 {external_refs}")

        workflow_rows = [
            {"工作流": graph, "节点": ref.name, "来源": _short_location(ref)}
            for graph, refs in index.workflow_nodes.items()
            for ref in refs
        ]
        if workflow_rows:
            compact_table(
                workflow_rows,
                height=240,
                key="architecture-workflow-table",
                column_order=["工作流", "节点", "来源"],
            )
        else:
            st.caption("没有可解析的工作流节点。")

        if index.eval_refs:
            st.markdown("**评测对象**")
            for name, ref in index.eval_refs.items():
                st.caption(f"`{name}` · `{ref.location}`")
