# -*- coding: utf-8 -*-
"""对话端：用户面。只有"已发布"的场景会出现在这里。

形态是常规对话页，不是入口大厅：左边一列入口（像会话列表），右边直接是对话。
没有选场景时落在第一个入口上，所以打开 `/chat` 就能直接说话。

每次运行都能展开"这次怎么答的"：调用链 + 每个模型/工具步骤属于哪个节点。
每个入口一条独立 thread，换入口 = 换会话，不会把上一个场景的记忆带过来。
页面状态都带 ``chat:`` 前缀，构建页 / 质量页各自独立。
"""
from __future__ import annotations

import uuid

import streamlit as st

from core.interfaces.console import routes
from core.interfaces.dashboard.chain import call_chain_dot
from core.interfaces.dashboard.common import load_agent
from core.interfaces.dashboard.traces import get_trace_events, render_trace_timeline
from core.quality.agent_eval import extract_final_answer
from core.scenarios import entry as entries
from core.scenarios import library


def render(route: routes.Route) -> None:
    published = entries.published_entries()
    if not published:
        _no_entries()
        return
    names = [item.name for item in published]
    requested = route.scenario
    if requested and requested not in names:
        _closed(requested)
        return
    current = requested or names[0]
    item = entries.load_entry(current)
    info = library.entry(current)
    if info is None or not item.enabled:
        _closed(current)
        return
    # 标题行留在顶层：Streamlit 只允许 columns 嵌一层，放进下面的分栏会报错。
    _header(item, info)
    # 入口列表放在内容左列（不再用 sidebar）：三个产品统一无 sidebar，
    # 切换产品时整条顶部导航不会横移。
    rail, panel = st.columns([1.05, 3.95], gap="large")
    with rail:
        _entry_rail(published, current)
    with panel:
        _conversation(current)


# ---------------------------------------------------------------- 入口与兜底


def _entry_rail(published: list[entries.ChatEntry], current: str) -> None:
    """左栏：已发布入口列表；当前入口高亮，点其它入口切过去。"""
    with st.container(key="chat-rail"):
        st.caption("对话入口")
        for item in published:
            info = library.entry(item.name)
            icon = info.icon if info else "💬"
            active = item.name == current
            if st.button(
                f"{icon} {item.display_title}",
                key=f"chat-open-{item.name}",
                type="primary" if active else "secondary",
                use_container_width=True,
            ):
                if not active:
                    routes.navigate("chat", item.name)
        st.caption("只列已发布的入口；在「构建 → 发布」里开放或撤回。")


def _no_entries() -> None:
    st.markdown("#### 💬 对话")
    st.info("还没有发布任何入口。")
    if st.button("去构建页发布", type="primary"):
        routes.navigate("build")


def _closed(name: str) -> None:
    st.markdown("#### 💬 对话")
    st.warning(f"入口 `{name}` 已关闭或不存在。")
    if st.button("回到默认入口", type="primary"):
        routes.navigate("chat")


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


def _pick_starter(name: str) -> None:
    """开场白 chip 回调：把选中那句话交给本轮发送，并清空选中态。

    清空必须发生在回调里：脚本跑起来之后 pill 已经实例化，再改它的 key 会报错；
    不清空的话下一轮会把同一句话再发一次。
    """
    key = f"chat-starter:{name}"
    picked = st.session_state.get(key)
    st.session_state[key] = None
    if picked:
        st.session_state[f"chat:pending:{name}"] = picked


def _conversation(name: str) -> None:
    item = entries.load_entry(name)
    info = library.entry(name)
    if info is None or not item.enabled:
        _closed(name)
        return

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
        with st.container(key="chat-starters"):
            st.pills(
                "可以这样开始",
                item.starters[:3],
                key=f"chat-starter:{name}",
                format_func=lambda value: value.split("\n")[0][:40],
                on_change=_pick_starter,
                args=(name,),
                selection_mode="single",
            )
    elif not _messages(name):
        st.caption("直接输入问题开始；回答下面可以展开「这次怎么答的」。")

    prompt = st.session_state.pop(f"chat:pending:{name}", None) or st.chat_input(
        "输入消息（Enter 发送）"
    )
    if not prompt:
        return
    _submit(name, str(prompt))


def _header(item: entries.ChatEntry, info: library.ScenarioEntry) -> None:
    left, right = st.columns([3.6, 2.4], vertical_alignment="center")
    with left:
        st.markdown(f"#### {info.icon} {item.display_title}")
        st.caption(item.tagline or info.description)
    buttons = right.columns(2)
    if buttons[0].button("新会话", key=f"chat-new:{item.name}", use_container_width=True):
        _new_thread(item.name)
        st.rerun()
    if buttons[1].button("在构建页打开", key=f"chat-edit:{item.name}", use_container_width=True):
        routes.navigate("build", item.name)


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
