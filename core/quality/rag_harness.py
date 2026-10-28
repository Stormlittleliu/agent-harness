# -*- coding: utf-8 -*-
"""能力层评测的 RAG 场景装配。

评测不直接 import retriever / Chroma：把注入的 retriever 包成 Scenario 工具，
再通过 FrameworkAgent.invoke_tool 调用。
"""
from __future__ import annotations

import json

from langchain_core.documents import Document

from core.agent.framework import FrameworkAgent
from core.llm.factory import chat_model
from core.agent.contracts import Scenario
from core.tools.rag.service import RagSummarizeService
from core.tools.rag.tools import build_rag_tools

EVAL_SYSTEM_PROMPT = "你是 RAG 问答助手。只依据工具返回的资料回答。"


def build_eval_agent(retriever) -> FrameworkAgent:
    service = RagSummarizeService(retriever=retriever)
    rag_summarize, rag_retrieve = build_rag_tools(service)
    scenario = Scenario(
        name="rag_eval",
        description="RAG capability eval",
        model=chat_model,
        system_prompt=EVAL_SYSTEM_PROMPT,
        tools=[rag_summarize, rag_retrieve],
        middleware=[],
        cases_path=None,
        high_risk_tools={},
        fallback_model=None,
        enable_todo=False,
        enable_summarization=False,
        tool_call_limit=None,
        pii_types=[],
        checkpoint=False,
        checkpoint_backend="memory",
        tool_policy={"default": "allow"},
        tool_timeout_seconds=60,
    )
    return FrameworkAgent(scenario)


def result_parts(result) -> tuple[str, dict]:
    """invoke_tool 返回 ToolMessage；兼容普通字符串返回。"""
    content = getattr(result, "content", result)
    artifact = getattr(result, "artifact", None)
    if not isinstance(artifact, dict):
        try:
            artifact = json.loads(content)
        except (TypeError, json.JSONDecodeError):
            artifact = {}
    return str(content), artifact


def docs_from_artifact(artifact: dict) -> list[Document]:
    docs = []
    for item in artifact.get("docs", []):
        metadata = dict(item.get("metadata") or {})
        metadata.setdefault("source", item.get("source", ""))
        if item.get("chunk_id") is not None:
            metadata.setdefault("chunk_id", item.get("chunk_id"))
        docs.append(Document(page_content=str(item.get("content", "")), metadata=metadata))
    return docs


def sources_from_artifact(artifact: dict) -> list[str]:
    return [str(item.get("source", "")) for item in artifact.get("docs", [])]
