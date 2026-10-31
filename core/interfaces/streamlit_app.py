import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from core.interfaces.react_agent import ReactAgent

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


def _message_text(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, list):
        return "".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return content if isinstance(content, str) else str(content)


def _last_ai_text(state) -> str:
    messages = state.get("messages") or []
    return _message_text(messages[-1]) if messages else ""


def _typewriter(generator, cache: list[str]):
    """逐字输出，同时缓存完整响应。"""
    for chunk in generator:
        cache.append(chunk)
        for char in chunk:
            yield char


def _render_pending_interrupt(agent, thread_id: str) -> None:
    """高风险工具被 HITL 拦截后，由用户决定批准或拒绝。"""
    if not st.session_state.get("pending_interrupt"):
        return

    st.warning("该操作属于高风险操作，需要人工审批后才会执行。")
    col_approve, col_reject = st.columns(2)

    if col_approve.button("批准执行", type="primary"):
        state = agent.resume(thread_id, [{"type": "approve"}])
        text = _last_ai_text(state)
        if text:
            st.session_state["messages"].append({"role": "assistant", "content": text})
        st.session_state.pop("pending_interrupt", None)
        st.rerun()

    if col_reject.button("拒绝执行"):
        state = agent.resume(thread_id, [{"type": "reject", "message": "用户拒绝执行"}])
        text = _last_ai_text(state)
        if text:
            st.session_state["messages"].append({"role": "assistant", "content": text})
        st.session_state.pop("pending_interrupt", None)
        st.rerun()


def run():
    st.set_page_config(page_title="智扫通 · 智能客服", page_icon="🤖")
    st.title("🤖 智扫通机器人智能客服")
    st.caption("基于 LangChain ReAct Agent + RAG 检索增强")
    st.divider()

    if "agent" not in st.session_state:
        with st.spinner("正在加载 Agent 与知识库..."):
            st.session_state["agent"] = ReactAgent()
    agent = st.session_state["agent"]

    if "thread_id" not in st.session_state:
        st.session_state["thread_id"] = f"web-{uuid.uuid4().hex}"
    if "messages" not in st.session_state:
        st.session_state["messages"] = []

    for message in st.session_state["messages"]:
        st.chat_message(message["role"]).write(message["content"])

    thread_id = st.session_state["thread_id"]
    _render_pending_interrupt(agent, thread_id)

    prompt = st.chat_input()
    if not prompt:
        return

    st.chat_message("user").write(prompt)
    st.session_state["messages"].append({"role": "user", "content": prompt})

    response_chunks: list[str] = []
    failed = False
    try:
        with st.spinner("智能客服思考中..."):
            stream = agent.execute_stream(prompt, thread_id=thread_id)
            st.chat_message("assistant").write_stream(_typewriter(stream, response_chunks))
    except Exception as exc:  # 页面不崩，错误可见
        failed = True
        st.error(f"请求失败：{type(exc).__name__}: {exc}")
        st.session_state["messages"].append({
            "role": "assistant",
            "content": "抱歉，本次请求执行失败，请稍后重试或查看终端日志。",
        })

    if failed:
        return

    answer = "".join(response_chunks).strip()
    if answer:
        st.session_state["messages"].append({"role": "assistant", "content": answer})
    else:
        st.warning("本次没有返回文本内容。")

    if getattr(agent.framework, "last_interrupt", None):
        st.session_state["pending_interrupt"] = True

    st.rerun()
