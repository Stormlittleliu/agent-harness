# -*- coding: utf-8 -*-
"""故障注入：超时、权限、参数错误、空检索、拒答评分。

这些测试不调用真实模型；它们验证 Harness 在异常输入下是否给出
可观察的 error ToolMessage，而不是让整个 run 崩掉。
"""
import time

from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import ToolMessage

from core.agent.middleware.generic import ValidateToolArgsMiddleware
from core.agent.middleware.policy import ToolPermissionMiddleware, ToolTimeoutMiddleware
from core.quality.metrics import score_case
from core.tools.rag.service import RagSummarizeService
from core.tools.rag.tools import build_rag_tools


def _request(name="demo", args=None):
    return ToolCallRequest(
        tool_call={
            "name": name,
            "args": args or {},
            "id": "call-1",
            "type": "tool_call",
        },
        tool=None,
        state={},
        runtime=None,
    )


def _ok(request):
    return ToolMessage(content="ok", tool_call_id=request.tool_call["id"], name=request.tool_call["name"])


def test_tool_timeout_returns_error_message():
    middleware = ToolTimeoutMiddleware(default_timeout=0.05)

    def slow(request):
        time.sleep(0.25)
        return _ok(request)

    result = middleware.wrap_tool_call(_request("slow"), slow)
    assert isinstance(result, ToolMessage)
    assert result.status == "error"
    assert "超时" in result.content


def test_permission_deny_does_not_call_handler():
    called = []
    middleware = ToolPermissionMiddleware({"deny": ["danger"]})

    def handler(request):
        called.append(True)
        return _ok(request)

    result = middleware.wrap_tool_call(_request("danger"), handler)
    assert called == []
    assert result.status == "error"
    assert "禁止执行" in result.content


def test_malformed_args_returns_correction_message():
    middleware = ValidateToolArgsMiddleware({
        "lookup": lambda args: "缺少 query" if not args.get("query") else None,
    })
    result = middleware.wrap_tool_call(_request("lookup", {}), _ok)
    assert result.status == "error"
    assert "参数校验失败" in result.content
    assert "缺少 query" in result.content


class _EmptyRetriever:
    def invoke(self, query):
        return []


def test_empty_retrieval_returns_empty_content_and_artifact():
    service = RagSummarizeService(retriever=_EmptyRetriever())
    tools = {tool.name: tool for tool in build_rag_tools(service)}
    result = tools["rag_retrieve"].invoke({
        "name": "rag_retrieve",
        "args": {"query": "不存在的资料", "k": 4},
        "id": "call-empty",
        "type": "tool_call",
    })
    assert result.content == ""
    assert result.artifact["docs"] == []
    assert service._format_context([]) == ""


def test_refusal_grader_accepts_empty_retrieval_answer():
    score = score_case(
        {"should_refuse": True, "expected_points": []},
        "资料中没有相关信息，无法回答。",
        [],
    )
    assert score["passed"] is True
    assert score["refused"] is True
