# -*- coding: utf-8 -*-
"""MultiHop-RAG Demo：把 609 篇语料做成检索工具，跑 FrameworkAgent。"""
from __future__ import annotations

import os
import re
import time

from langchain_core.documents import Document
from langchain_core.tools import tool

from core.agent.contracts import Scenario
from core.agent.framework import FrameworkAgent
from core.llm.factory import chat_model
from core.quality.datasets import build_store
from core.quality.metrics import score_retrieval
from core.tools.rag.embedding import LazyLocalEmbeddings
from core.tools.rag.retrievers import ChunkIdRetriever, KeywordBM25Retriever, TopKEnsembleRetriever
from core.tools.rag.service import RagSummarizeService

_STORES = {}
_DOCS: list[Document] = []


def _artifact(query: str, docs) -> dict:
    return {
        "query": query,
        "docs": [
            {
                "rank": index,
                "source": os.path.basename(str((doc.metadata or {}).get("source", ""))),
                "chunk_id": (doc.metadata or {}).get("chunk_id"),
                "content": doc.page_content,
                "metadata": doc.metadata or {},
            }
            for index, doc in enumerate(docs, 1)
        ],
    }


def get_store(corpus, embedding_name: str | None = None):
    global _DOCS
    key = embedding_name or "default"
    if key in _STORES:
        return _STORES[key]
    if not _DOCS:
        _DOCS = [
            Document(
                page_content=f"{item.get('title', '')}\n\n{item.get('body', '')}",
                metadata={
                    "source": item.get("title", ""),
                    "title": item.get("title", ""),
                    "chunk_id": f"doc-{index}",
                },
            )
            for index, item in enumerate(corpus)
        ]
    embedding = None
    if embedding_name == "en":
        from pathlib import Path
        model_path = Path(__file__).resolve().parents[2] / "data" / "models" / "bge-small-en-v1.5"
        if model_path.exists():
            embedding = LazyLocalEmbeddings(str(model_path))
        else:
            print("[warn] bge-small-en-v1.5 不存在，回退中文 BGE")
    _STORES[key] = build_store(f"demo_multihop_{key}_{int(time.time())}", _DOCS, embedding_function=embedding)
    return _STORES[key]


def _en_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def build_retriever(corpus, kind: str = "vector", k: int = 4, embedding_name: str | None = None):
    store = get_store(corpus, embedding_name=embedding_name)
    vector = store.as_retriever(search_kwargs={"k": k})
    if kind == "vector":
        return vector
    return TopKEnsembleRetriever(
        retrievers=[
            ChunkIdRetriever(inner=vector),
            KeywordBM25Retriever(
                corpus_loader=lambda: _DOCS,
                k=k,
                tokenize=_en_tokens,
            ),
        ],
        weights=[0.6, 0.4],
        id_key="chunk_id",
        k=k,
    )


def build_agent(corpus, system_prompt: str, kind: str = "vector", k: int = 4, embedding_name: str | None = None):
    retriever = build_retriever(corpus, kind=kind, k=k, embedding_name=embedding_name)
    service = RagSummarizeService(retriever=retriever)

    @tool(
        "rag_retrieve",
        description="检索 MultiHop 新闻语料，返回原始资料片段；可以多次调用不同子查询。",
        response_format="content_and_artifact",
    )
    def rag_retrieve(query: str, top_k: int = k):
        docs = service.retriever_docs(query)[:top_k]
        content = "\n\n".join(doc.page_content[:1500] for doc in docs)
        return content, _artifact(query, docs)

    scenario = Scenario(
        name="multihop_demo",
        description="MultiHop-RAG retrieval demo",
        model=chat_model,
        system_prompt=system_prompt,
        tools=[rag_retrieve],
        middleware=[],
        context={},
        cases_path=None,
        enable_todo=False,
        enable_summarization=False,
        tool_call_limit=6,
        token_budget=80000,
        pii_types=[],
        checkpoint=False,
        tool_policy={"default": "allow"},
    )
    return FrameworkAgent(scenario)


def _answer_text(messages):
    for message in reversed(messages):
        if getattr(message, "type", "") == "ai":
            content = getattr(message, "content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""


def run_case(agent, case) -> dict:
    state = agent.invoke(case["question"])
    calls = []
    for message in state["messages"]:
        artifact = getattr(message, "artifact", None)
        if not isinstance(artifact, dict):
            continue
        sources = [str(item.get("source", "")) for item in artifact.get("docs", [])]
        calls.append({"query": artifact.get("query", ""), "sources": sources})

    if not calls:
        return {
            "id": case["id"],
            "question": case["question"], "question_type": case["question_type"],
            "passed": False, "hit": False, "mrr": 0.0,
            "failure_type": "no_tool_call", "calls": [], "answer": _answer_text(state["messages"]),
            "trace_id": agent.last_trace_id,
        }

    best_mrr = 0.0
    hit_any = False
    for call in calls:
        hit, mrr = score_retrieval(call["sources"][:4], case["evidence_titles"])
        hit_any = hit_any or bool(hit)
        best_mrr = max(best_mrr, float(mrr or 0.0))

    return {
        "id": case["id"],
        "question": case["question"], "question_type": case["question_type"],
        "passed": hit_any, "hit": hit_any, "mrr": best_mrr,
        "failure_type": None if hit_any else "retrieval_miss",
        "calls": calls, "answer": _answer_text(state["messages"]),
        "trace_id": agent.last_trace_id,
    }
