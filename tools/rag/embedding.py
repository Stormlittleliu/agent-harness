# -*- coding: utf-8 -*-
"""Embedding provider：本地 BGE / DashScope。

放在 tools/rag 下，和 RAG 工具一起；model/factory.py 只保留 chat model。
"""
from __future__ import annotations

from pathlib import Path

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_core.embeddings import Embeddings

from utils.config_handler import rag_conf


class LazyLocalEmbeddings(Embeddings):
    """延迟初始化本地 sentence-transformers 模型，避免 import 阶段就加载权重。"""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._impl = None

    def _get_impl(self):
        if self._impl is None:
            from langchain_huggingface import HuggingFaceEmbeddings

            from utils.path_tool import get_abs_path

            model_path = self.model_name
            if not Path(model_path).is_absolute():
                model_path = get_abs_path(model_path)

            self._impl = HuggingFaceEmbeddings(
                model_name=model_path,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        return self._impl

    def embed_documents(self, texts):
        return self._get_impl().embed_documents(texts)

    def embed_query(self, text):
        return self._get_impl().embed_query(text)


class EmbeddingsFactory:
    def generator(self) -> Embeddings:
        provider = str(rag_conf.get("embedding_provider", "dashscope")).lower()
        if provider == "local":
            return LazyLocalEmbeddings(rag_conf["embedding_model_name"])
        return DashScopeEmbeddings(model=rag_conf["embedding_model_name"])


embed_model = EmbeddingsFactory().generator()
