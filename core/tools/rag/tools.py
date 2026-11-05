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

from core.tools.rag.service import RagSummarizeService


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


def build_rag_tools(
    service: RagSummarizeService | None = None,
    *,
    where: dict | None = None,
    summarize_name: str = "rag_summarize",
    retrieve_name: str = "rag_retrieve",
):
    """按 service / where 构造 RAG 工具；名字可覆盖，便于同一 toolbox 放多套域。

    ``where={"domain": "clothing"}`` 时，向量检索和 BM25 语料都只取服装分块；
    不传则查全库（通用调试用）。
    """
    service = service or RagSummarizeService(where=where)

    @tool(
        summarize_name,
        description="从向量存储中检索参考资料并总结回答",
        response_format="content_and_artifact",
    )
    def rag_summarize(query: str):
        answer, docs = service.rag_summarize_with_docs(query)
        return answer, _artifact(query, docs)

    @tool(
        retrieve_name,
        description="检索知识库并返回原始资料片段（评测用）",
        response_format="content_and_artifact",
    )
    def rag_retrieve(query: str, k: int = 4):
        docs = service.retriever_docs(query)[:k]
        content = "\n\n".join(doc.page_content for doc in docs)
        return content, _artifact(query, docs)

    return rag_summarize, rag_retrieve
