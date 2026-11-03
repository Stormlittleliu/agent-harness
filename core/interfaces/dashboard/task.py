# -*- coding: utf-8 -*-
"""任务执行视图：输入任务，查看回答、工具调用、trace、对象与 HITL。"""
from __future__ import annotations

import json
import uuid

import streamlit as st

from core.agent.framework import FrameworkAgent
from core.interfaces.dashboard.common import short_text
from core.interfaces.dashboard.layout import (
    Kpi,
    compact_table,
    kpi_row,
    master_detail,
    page_header,
    section,
    text_block,
)
from core.interfaces.dashboard.objects import build_object_index, render_case_object_panel
from core.interfaces.dashboard.traces import get_trace_events, render_trace_timeline
from core.quality.agent_eval import extract_final_answer, extract_tool_calls


def _tool_rows(messages, events: list[dict], index) -> list[dict]:
    end_by_tool: dict[str, dict] = {}
    for event in events:
        if event.get("event") in {"tool_end", "tool_error"} and event.get("tool"):
            end_by_tool[str(event["tool"])] = event
    rows = []
    for call in extract_tool_calls(messages):
        name = str(call.get("name") or "")
        end = end_by_tool.get(name) or {}
        ref = index.tools.get(name)
        rows.append({
            "工具": name,
            "参数": short_text(json.dumps(call.get("args", {}), ensure_ascii=False), 90),
            "状态": end.get("status") or ("error" if end.get("event") == "tool_error" else "—"),
            "耗时": f"{end.get('latency_ms')}ms" if end.get("latency_ms") is not None else "—",
            "源码": ref.location if ref else "—",
        })
    return rows


def _dot_escape(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace('"', "'").replace("\n", "\\n")


def _call_chain_dot(events: list[dict], messages: list, interrupted: bool = False) -> str:
    """把 trace 事件画成 用户问题 → 模型/工具 → 最终回答 的调用链。

    优先用 trace 的时序；没有 trace 时退回 messages 里的 tool_calls。
    工具节点在 `tool_start` 时创建，`tool_end/tool_error` 时补状态和耗时。
    """
    nodes: list[list[str]] = []
    edges: list[tuple[str, str]] = []

    def add(label: str, kind: str) -> int:
        node_id = f"n{len(nodes)}"
        nodes.append([node_id, label, kind])
        if len(nodes) > 1:
            edges.append((nodes[-2][0], node_id))
        return len(nodes) - 1

    add("用户问题", "start")
    model_no = 0
    tool_starts: dict[str, list[int]] = {}
    processed = False
    truncated = False

    def can_add() -> bool:
        nonlocal truncated
        if len(nodes) >= 30:
            truncated = True
            return False
        return True

    for event in events:
        name = event.get("event")
        if name == "model_end":
            model_no += 1
            if not can_add():
                break
            label = f"模型 #{model_no}"
            meta = []
            tokens = event.get("total_tokens")
            if tokens:
                meta.append(f"{int(tokens)} tok")
            latency = event.get("latency_ms")
            if latency is not None:
                meta.append(f"{float(latency):.0f} ms")
            if meta:
                label += "\n" + " · ".join(meta)
            add(label, "model")
            processed = True
        elif name == "tool_start":
            if not can_add():
                break
            tool = str(event.get("tool") or "tool")
            index = add(f"工具: {tool}\n运行中", "tool")
            tool_starts.setdefault(tool, []).append(index)
            processed = True
        elif name in {"tool_end", "tool_error"}:
            tool = str(event.get("tool") or "tool")
            status = str(event.get("status") or ("error" if name == "tool_error" else "完成"))
            label = f"工具: {tool}\n{status}"
            latency = event.get("latency_ms")
            if latency is not None:
                label += f" · {float(latency):.0f} ms"
            kind = "tool_error" if name == "tool_error" or status == "error" else "tool"
            stack = tool_starts.get(tool) or []
            if stack:
                index = stack.pop()
                nodes[index][1] = label
                nodes[index][2] = kind
            elif can_add():
                add(label, kind)
            processed = True
        elif name == "model_error":
            if can_add():
                add("模型错误", "error")
            processed = True

    if not processed:
        for message in messages:
            calls = getattr(message, "tool_calls", None) or []
            if not calls:
                continue
            if not can_add():
                break
            model_no += 1
            add(f"模型 #{model_no}", "model")
            for call in calls:
                if not can_add():
                    break
                tool = call.get("name") if isinstance(call, dict) else getattr(call, "name", "tool")
                add(f"工具: {tool}", "tool")
        if model_no == 0:
            add("模型 #1", "model")

    if truncated:
        add("…更多步骤", "more")
    if interrupted:
        add("等待人工审批", "hitl")
    else:
        add("最终回答", "end")

    colors = {
        "start": "#E3F2FD",
        "model": "#E8EAF6",
        "tool": "#E8F5E9",
        "tool_error": "#FFEBEE",
        "error": "#FFEBEE",
        "hitl": "#FFF3E0",
        "more": "#F5F5F5",
        "end": "#E8F5E9",
    }
    lines = [
        "digraph G {",
        "rankdir=LR;",
        "graph [nodesep=0.25, ranksep=0.35];",
        'node [shape=box, style="rounded,filled", fontsize=10, fontname="Microsoft YaHei"];',
    ]
    for node_id, label, kind in nodes:
        shape = "oval" if kind in {"start", "end"} else "box"
        fill = colors.get(kind, "#F5F5F5")
        lines.append(
            f'"{node_id}" [label="{_dot_escape(label)}", shape={shape}, fillcolor="{fill}"];'
        )
    for source, target in edges:
        lines.append(f'"{source}" -> "{target}";')
    lines.append("}")
    return "\n".join(lines)


def _render_hitl(agent: FrameworkAgent, task: dict) -> bool:
    """有 interrupt 时渲染审批按钮；返回是否已触发 resume。"""
    if not task.get("state", {}).get("__interrupt__"):
        return False
    st.warning("高风险操作被 HITL 拦截，需要人工审批。")
    col_approve, col_reject = st.columns(2, gap="small")
    decision = None
    if col_approve.button("批准执行", key="task-approve"):
        decision = {"type": "approve"}
    if col_reject.button("拒绝执行", key="task-reject"):
        decision = {"type": "reject", "message": "用户拒绝执行"}
    if not decision:
        return False
    try:
        final_state = agent.resume(task["thread_id"], [decision])
    except Exception as exc:  # noqa: BLE001
        st.error(f"恢复执行失败：{type(exc).__name__}: {exc}")
        return False
    task["state"] = final_state
    task["trace_id"] = agent.last_trace_id
    st.session_state["last_task"] = task
    st.rerun()
    return True


def render_task(agent: FrameworkAgent, examples: list[str] | None = None) -> None:
    page_header(
        "任务执行",
        "输入任务，查看 Agent 选了什么工具、走了多少步、花了多少 token；右侧可切到对象链路。",
        meta="运行会调用模型；其余视图只读已有文件。",
    )

    if "task_query" not in st.session_state:
        st.session_state["task_query"] = ""
    examples = examples or []
    with st.container(border=True):
        query = st.text_area("任务", key="task_query", height=82)
        actions = st.columns([1, 1, 3], gap="small", vertical_alignment="center")
        run = actions[0].button("运行 Agent", type="primary", use_container_width=True)
        if examples:
            with actions[1].popover("示例任务"):
                for example in examples:
                    st.code(example, language="text")
    if run and query.strip():
        thread_id = f"ui-{uuid.uuid4().hex}"
        try:
            with st.spinner("Agent 执行中..."):
                state = agent.invoke(query.strip(), thread_id=thread_id)
            st.session_state["last_task"] = {
                "query": query.strip(),
                "thread_id": thread_id,
                "state": state,
                "trace_id": agent.last_trace_id,
            }
        except Exception as exc:  # noqa: BLE001
            st.error(f"执行失败：{type(exc).__name__}: {exc}")
            return

    task = st.session_state.get("last_task")
    if not task:
        st.caption("还没有运行任务；先输入问题或从示例任务开始。")
        return

    state = task["state"]
    events, trace_issue = get_trace_events(task.get("trace_id"))
    end = next((event for event in events if event.get("event") == "run_end"), {})
    messages = state.get("messages") or []
    answer = extract_final_answer(messages)
    tool_calls = extract_tool_calls(messages)
    tool_names = [str(call.get("name")) for call in tool_calls if call.get("name")]
    trace_id = task.get("trace_id")
    row = {
        "id": task.get("thread_id"),
        "category": "task",
        "question": task.get("query", ""),
        "expected_tools": [],
        "tool_names": tool_names,
        "tool_calls": tool_calls,
        "trace_id": trace_id,
        "answer": answer,
        "passed": None,
    }
    index = build_object_index(agent)

    kpi_row(
        [
            Kpi("状态", end.get("status", "—")),
            Kpi("模型 / 工具", f"{end.get('model_calls', '—')} / {end.get('tool_calls', '—')}"),
            Kpi("Token", f"{int(end.get('total_tokens') or 0):,}"),
            Kpi(
                "耗时 / 成本",
                f"{(end.get('duration_ms') or 0) / 1000:.1f}s / ¥{float(end.get('cost_est') or 0):.4f}",
            ),
        ]
    )
    if trace_issue:
        st.caption(f"trace：{trace_issue}")

    section("可视化调用链", "用户问题 → 模型 / 工具步骤 → 最终回答；红色表示错误，橙色表示等待审批。")
    chain = _call_chain_dot(
        events,
        messages,
        interrupted=bool(state.get("__interrupt__")),
    )
    with st.container(border=True):
        st.graphviz_chart(chain, use_container_width=True)

    left, right = master_detail(0.62)
    with left:
        section("最终回答")
        text_block(answer or "（无文本回答）", height=220)

        section("工具调用")
        rows = _tool_rows(messages, events, index)
        if rows:
            compact_table(
                rows,
                height=240,
                key="task-tool-table",
                column_order=["工具", "参数", "状态", "耗时", "源码"],
            )
        else:
            st.caption("本次运行没有调用工具。")

        todos = state.get("todos") or []
        if todos:
            section("任务清单")
            compact_table(
                [
                    {
                        "内容": todo.get("content", "") if isinstance(todo, dict) else str(todo),
                        "状态": todo.get("status", "") if isinstance(todo, dict) else "",
                    }
                    for todo in todos
                ],
                height=180,
                key="task-todo-table",
            )

    with right:
        if _render_hitl(agent, task):
            return
        mode = st.radio(
            "查看",
            ["轨迹", "对象", "原始"],
            horizontal=True,
            key="task-detail-mode",
        )
        if mode == "轨迹":
            section("执行轨迹")
            render_trace_timeline(trace_id)
        elif mode == "对象":
            render_case_object_panel(agent, row, index=index)
        else:
            section("原始 trace")
            with st.container(height=320):
                st.json(events, expanded=False)
