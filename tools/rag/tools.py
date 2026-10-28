# -*- coding: utf-8 -*-
"""RAG 工具：检索与总结。

- `rag_summarize`：检索 + LLM 总结，业务场景使用；
- `rag_retrieve`：只返回原始检索片段，评测/调试使用；
- 两者都返回 `content_and_artifact`：模型只看到 content，评测从 artifact 读取
  docs / rank / source，不污染模型上下文。
"""
from __future__ import annotations

import os

from langchain_core.tools import tool

from tools.rag.service import RagSummarizeService


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


def build_rag_tools(service: RagSummarizeService | None = None):
    """按 service 构造 RAG 工具；不传 service 时使用业务持久化向量库。"""
    service = service or RagSummarizeService()

    @tool(
        "rag_summarize",
        description="从向量存储中检索参考资料并总结回答",
        response_format="content_and_artifact",
    )
    def rag_summarize(query: str):
        answer, docs = service.rag_summarize_with_docs(query)
        return answer, _artifact(query, docs)

    @tool(
        "rag_retrieve",
        description="检索知识库并返回原始资料片段（评测用）",
        response_format="content_and_artifact",
    )
    def rag_retrieve(query: str, k: int = 4):
        docs = service.retriever_docs(query)[:k]
        content = "\n\n".join(doc.page_content for doc in docs)
        return content, _artifact(query, docs)

    return rag_summarize, rag_retrieve
