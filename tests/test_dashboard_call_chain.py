# -*- coding: utf-8 -*-
"""任务执行调用链的离线测试：trace 事件 / messages 回退。"""
from langchain_core.messages import AIMessage

from core.interfaces.dashboard.task import _call_chain_dot


def test_call_chain_from_trace_events():
    events = [
        {"event": "model_end", "total_tokens": 100, "latency_ms": 1200},
        {"event": "tool_start", "tool": "search_notes"},
        {"event": "tool_end", "tool": "search_notes", "status": "completed", "latency_ms": 80},
        {"event": "model_end", "total_tokens": 50, "latency_ms": 600},
    ]
    dot = _call_chain_dot(events, [], interrupted=False)
    assert dot.startswith("digraph")
    assert "用户问题" in dot
    assert "search_notes" in dot
    assert "completed" in dot
    assert "最终回答" in dot


def test_call_chain_falls_back_to_messages():
    message = AIMessage(
        content="",
        tool_calls=[{
            "name": "read_file",
            "args": {"path": "README.md"},
            "id": "call-1",
            "type": "tool_call",
        }],
    )
    dot = _call_chain_dot([], [message], interrupted=False)
    assert "read_file" in dot
    assert "最终回答" in dot


def test_call_chain_stops_at_hitl():
    events = [{"event": "model_end", "total_tokens": 10, "latency_ms": 100}]
    dot = _call_chain_dot(events, [], interrupted=True)
    assert "等待人工审批" in dot
    assert "最终回答" not in dot


def test_call_chain_marks_langgraph_node():
    """每一步都要说清它属于哪个工作流节点，并带上悬停说明。"""
    events = [
        {"event": "model_end", "total_tokens": 10, "latency_ms": 100, "node": "verify"},
        {"event": "tool_start", "tool": "list_notes", "node": "verify"},
        {"event": "tool_end", "tool": "list_notes", "status": "completed", "latency_ms": 5, "node": "verify"},
    ]
    dot = _call_chain_dot(events, [], scenario="robot_vacuum")
    assert "复核 · verify" in dot
    assert "tooltip=" in dot


def test_call_chain_falls_back_for_unknown_node():
    events = [{"event": "model_end", "total_tokens": 10, "node": "mystery_step"}]
    dot = _call_chain_dot(events, [], scenario="robot_vacuum")
    assert "节点 mystery_step" in dot
