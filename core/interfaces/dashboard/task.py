# -*- coding: utf-8 -*-
"""任务执行视图：输入任务，查看工具调用、trace 与运行指标。"""
from __future__ import annotations

import json
import uuid

import streamlit as st
from langchain_core.messages import ToolMessage

from core.agent.framework import FrameworkAgent
from core.interfaces.dashboard.common import ROOT
from core.observability.trace_report import load_events
from core.quality.agent_eval import extract_final_answer, message_text

TRACE_DIR = ROOT / "outputs" / "traces"


def trace_events(trace_id: str | None) -> list[dict]:
    if not trace_id:
        return []
    return [event for event in load_events(TRACE_DIR) if event.get("trace_id") == trace_id]


def _tool_rows(messages) -> list[dict]:
    results = {
        getattr(message, "tool_call_id", None): message_text(message)
        for message in messages
        if isinstance(message, ToolMessage)
    }
    rows = []
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            data = call if isinstance(call, dict) else call.model_dump()
            rows.append({
                "工具": data.get("name", ""),
                "参数": json.dumps(data.get("args", {}), ensure_ascii=False),
                "结果": results.get(data.get("id"), "")[:160],
            })
    return rows


def render_task(agent: FrameworkAgent, examples: list[str] | None = None) -> None:
    st.caption("输入任务，查看 Agent 选了什么工具、走了多少步、花了多少 token。")

    if "task_query" not in st.session_state:
        st.session_state["task_query"] = ""
    examples = examples or []
    if examples:
        cols = st.columns(len(examples))
        for index, example in enumerate(examples):
            if cols[index].button(example, key=f"task-example-{index}"):
                st.session_state["task_query"] = example
                st.rerun()

    query = st.text_area("任务", key="task_query", height=90)
    if st.button("运行 Agent", type="primary") and query.strip():
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
        except Exception as exc:  # noqa: BLE001 - 展示为页面错误而非 traceback
            st.error(f"执行失败：{type(exc).__name__}: {exc}")
            return

    task = st.session_state.get("last_task")
    if not task:
        return

    state = task["state"]
    try:
        events = trace_events(task["trace_id"])
    except Exception as exc:  # noqa: BLE001
        events = []
        st.warning(f"trace 读取失败：{type(exc).__name__}: {exc}")
    end = next((event for event in events if event.get("event") == "run_end"), {})

    st.subheader("运行结果")
    cols = st.columns(6)
    cols[0].metric("状态", end.get("status", "-"))
    cols[1].metric("模型调用", end.get("model_calls", "-"))
    cols[2].metric("工具调用", end.get("tool_calls", "-"))
    cols[3].metric("Token", f"{end.get('total_tokens') or 0:,}")
    cols[4].metric("耗时", f"{(end.get('duration_ms') or 0) / 1000:.1f}s")
    cost = float(end.get("cost_est") or 0)
    cols[5].metric("成本", f"¥{cost:.4f}" if cost else "未配置单价")

    messages = state.get("messages") or []
    answer = extract_final_answer(messages)
    st.markdown("**最终回答**")
    st.chat_message("assistant").write(answer or "（无文本回答）")

    todos = state.get("todos") or []
    if todos:
        st.markdown("**任务清单**")
        st.dataframe(
            [
                {
                    "内容": todo.get("content", "") if isinstance(todo, dict) else str(todo),
                    "状态": todo.get("status", "") if isinstance(todo, dict) else "",
                }
                for todo in todos
            ],
            use_container_width=True,
            hide_index=True,
        )

    rows = _tool_rows(messages)
    if rows:
        st.markdown("**工具调用**")
        st.dataframe(rows, use_container_width=True, hide_index=True)

    if state.get("__interrupt__"):
        st.warning("高风险操作被 HITL 拦截，需要人工审批。")
        col_approve, col_reject = st.columns(2)
        decision = None
        if col_approve.button("批准执行", key="task-approve"):
            decision = {"type": "approve"}
        if col_reject.button("拒绝执行", key="task-reject"):
            decision = {"type": "reject", "message": "用户拒绝执行"}
        if decision:
            try:
                final_state = agent.resume(task["thread_id"], [decision])
            except Exception as exc:  # noqa: BLE001
                st.error(f"恢复执行失败：{type(exc).__name__}: {exc}")
                return
            task["state"] = final_state
            task["trace_id"] = agent.last_trace_id
            st.session_state["last_task"] = task
            st.rerun()

    if events:
        st.markdown("**执行轨迹**")
        timeline = []
        for event in events:
            name = event.get("event")
            if name == "model_end":
                detail = (
                    f"{event.get('model')} · {event.get('prompt_tokens')}/"
                    f"{event.get('completion_tokens')} tokens · {event.get('latency_ms')}ms"
                )
                timeline.append({"时间": event.get("ts"), "事件": "模型调用", "详情": detail})
            elif name == "tool_start":
                timeline.append({
                    "时间": event.get("ts"),
                    "事件": "工具开始",
                    "详情": f"{event.get('tool')} · {str(event.get('input', ''))[:80]}",
                })
            elif name == "tool_end":
                detail = f"{event.get('tool')} · {event.get('status')} · {event.get('latency_ms')}ms"
                timeline.append({"时间": event.get("ts"), "事件": "工具结束", "详情": detail})
            elif name in {"tool_error", "model_error"}:
                timeline.append({
                    "时间": event.get("ts"),
                    "事件": "错误",
                    "详情": str(event.get("error", ""))[:120],
                })
        st.dataframe(timeline, use_container_width=True, hide_index=True)

        with st.expander("原始 trace JSON"):
            st.json(events)
