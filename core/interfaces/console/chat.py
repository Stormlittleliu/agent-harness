# -*- coding: utf-8 -*-
"""对话端：用户面。只有"已发布"的场景会出现在这里。

和旧「任务执行」的区别：

- 这是**多轮**会话：同一个 thread_id 连续对话，记忆由 checkpointer 保留；
- 每次运行都能展开"这次怎么答的"：调用链 + 每个模型/工具步骤属于哪个节点；
- 每个场景一条独立会话，换场景 = 换 thread，不会把上一个场景的记忆带过来；
- 页面自己的状态都带 ``chat:`` 前缀，构建页 / 质量页各自独立。

入口页（没选场景）只读 entry.yml，不加载任何 Agent，所以打开很快。
"""
from __future__ import annotations

import uuid

import streamlit as st

from core.interfaces.console import routes
from core.interfaces.dashboard.chain import call_chain_dot
from core.interfaces.dashboard.common import load_agent
from core.interfaces.dashboard.layout import page_header
from core.interfaces.dashboard.traces import get_trace_events, render_trace_timeline
from core.quality.agent_eval import extract_final_answer
from core.scenarios import entry as entries
from core.scenarios import library


def render(route: routes.Route) -> None:
    if not route.scenario:
        _gallery()
    else:
        _conversation(route.scenario)


# ---------------------------------------------------------------- 入口页


def _gallery() -> None:
    published = entries.published_entries()
    page_header(
        "对话",
        "选一个入口开始。这里只显示已发布的场景——场景在「构建 → 发布」里开放，"
        "没发布的东西不会出现在用户面前。",
        meta=f"已发布 {len(published)} 个",
    )
    if not published:
        st.info("还没有发布任何入口。去「构建」打开一个场景，在「发布」页签把它开放出来。")
        if st.button("去构建", type="primary"):
            routes.navigate("build")
        return

    columns = st.columns(3, gap="medium")
    for index, item in enumerate(published):
        info = library.entry(item.name)
        icon = info.icon if info else "💬"
        description = item.tagline or (info.description if info else "")
        with columns[index % 3]:
            with st.container(border=True):
                st.markdown(f"#### {icon} {item.display_title}")
                st.caption(description)
                if item.starters:
                    st.caption("试试：" + " ｜ ".join(item.starters[:2]))
                if st.button(
                    "开始对话",
                    key=f"chat-open-{item.name}",
                    type="primary",
                    use_container_width=True,
                ):
                    routes.navigate("chat", item.name)


# ---------------------------------------------------------------- 会话页


def _messages(name: str) -> list[dict]:
    return st.session_state.setdefault(f"chat:messages:{name}", [])


def _thread_id(name: str) -> str:
    key = f"chat:thread:{name}"
    if key not in st.session_state:
        st.session_state[key] = f"web-{uuid.uuid4().hex}"
    return str(st.session_state[key])


def _interrupt_key(name: str) -> str:
    return f"chat:interrupt:{name}"


def _new_thread(name: str) -> None:
    st.session_state[f"chat:thread:{name}"] = f"web-{uuid.uuid4().hex}"
    st.session_state[f"chat:messages:{name}"] = []
    st.session_state.pop(_interrupt_key(name), None)


def _conversation(name: str) -> None:
    item = entries.load_entry(name)
    info = library.entry(name)
    if info is None or not item.enabled:
        st.warning(f"入口 `{name}` 已关闭或不存在。")
        if st.button("返回对话入口", type="primary"):
            routes.navigate("chat")
        return

    _header(item, info)
    for message in _messages(name):
        with st.chat_message(message["role"]):
            st.markdown(message.get("content") or "—")
            trace_id = message.get("trace_id")
            if message["role"] == "assistant" and trace_id:
                with st.expander("这次怎么答的"):
                    _trace_panel(name, trace_id)

    if _render_interrupt(name):
        return

    if not _messages(name) and item.starters:
        st.caption("可以从这些开始：")
        starter_cols = st.columns(min(3, len(item.starters)))
        for index, starter in enumerate(item.starters[:3]):
            if starter_cols[index].button(
                starter.split("\n")[0][:40],
                key=f"chat-starter-{name}-{index}",
                use_container_width=True,
            ):
                st.session_state[f"chat:pending:{name}"] = starter

    prompt = st.session_state.pop(f"chat:pending:{name}", None) or st.chat_input(
        "输入消息（Enter 发送）"
    )
    if not prompt:
        return
    _submit(name, str(prompt))


def _header(item: entries.ChatEntry, info: library.ScenarioEntry) -> None:
    left, right = st.columns([3.2, 2.4], vertical_alignment="center")
    with left:
        st.markdown(f"#### {info.icon} {item.display_title}")
        st.caption(item.tagline or info.description)
    with right:
        published = entries.published_names()
        current = published.index(item.name) if item.name in published else 0
        picked = st.selectbox(
            "切换入口",
            published,
            index=current,
            format_func=lambda value: entries.load_entry(value).display_title,
            key=f"chat:pick:{item.name}",
            label_visibility="collapsed",
        )
        if picked != item.name:
            routes.navigate("chat", picked)
        buttons = st.columns(2)
        if buttons[0].button("新会话", key=f"chat-new:{item.name}", use_container_width=True):
            _new_thread(item.name)
            st.rerun()
        if buttons[1].button("返回入口", key=f"chat-back:{item.name}", use_container_width=True):
            routes.navigate("chat")


def _submit(name: str, prompt: str) -> None:
    """跑一轮：用户消息 → Agent → 回答 / 审批。异常也记进历史，刷新不丢。"""
    messages = _messages(name)
    messages.append({"role": "user", "content": prompt})
    agent = _agent(name)
    thread_id = _thread_id(name)
    try:
        with st.spinner("Agent 执行中…"):
            state = agent.invoke(prompt, thread_id=thread_id)
    except Exception as exc:  # noqa: BLE001 - 页面不崩，错误留在会话里
        messages.append({"role": "assistant", "content": f"执行失败：{type(exc).__name__}: {exc}"})
        st.rerun()
        return

    answer = extract_final_answer(state.get("messages") or [])
    if state.get("__interrupt__"):
        st.session_state[_interrupt_key(name)] = {
            "thread_id": thread_id,
            "trace_id": agent.last_trace_id,
        }
        if answer:
            messages.append(
                {"role": "assistant", "content": answer, "trace_id": agent.last_trace_id}
            )
    else:
        messages.append(
            {
                "role": "assistant",
                "content": answer or "（这一步没有文本回答，展开可以看执行过程）",
                "trace_id": agent.last_trace_id,
            }
        )
    st.rerun()


def _render_interrupt(name: str) -> bool:
    """高风险操作被 HITL 拦下：只给批准 / 拒绝，不再接受新消息。"""
    pending = st.session_state.get(_interrupt_key(name))
    if not pending:
        return False
    st.warning("这一步需要人工审批后才会执行（高风险工具）。")
    approve, reject = st.columns(2)
    decision = None
    if approve.button("批准执行", key=f"chat-approve:{name}", type="primary", use_container_width=True):
        decision = {"type": "approve"}
    if reject.button("拒绝执行", key=f"chat-reject:{name}", use_container_width=True):
        decision = {"type": "reject", "message": "用户拒绝执行"}
    if not decision:
        return True

    agent = _agent(name)
    try:
        with st.spinner("继续执行…"):
            state = agent.resume(pending["thread_id"], [decision])
    except Exception as exc:  # noqa: BLE001
        st.error(f"恢复执行失败：{type(exc).__name__}: {exc}")
        return True
    answer = extract_final_answer(state.get("messages") or [])
    _messages(name).append(
        {
            "role": "assistant",
            "content": answer or "（审批后没有文本回答）",
            "trace_id": agent.last_trace_id,
        }
    )
    st.session_state.pop(_interrupt_key(name), None)
    st.rerun()
    return True


def _agent(name: str):
    with st.spinner("正在加载场景与知识库…"):
        return load_agent(name)


def _trace_panel(name: str, trace_id: str) -> None:
    """一次运行的调用链 + 逐条事件；节点悬停能看到它在做什么。"""
    events, issue = get_trace_events(trace_id)
    if issue and issue != "not-found":
        st.caption(f"trace 读取失败：{issue}")
    dot = call_chain_dot(events, [], interrupted=False, scenario=name)
    with st.container(border=True):
        st.graphviz_chart(dot, use_container_width=True)
    render_trace_timeline(trace_id)
