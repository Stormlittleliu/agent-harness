# -*- coding: utf-8 -*-
"""模型工厂：请求超时必须来自配置，而不是事后赋值。"""
from core.llm.factory import chat_model
from core.utils.config_handler import rag_conf


def test_request_timeout_in_config():
    assert float(rag_conf.get("request_timeout", 0)) == 60


def test_chat_model_built_with_request_timeout():
    provider = str(rag_conf.get("chat_provider", "")).lower()
    if provider == "deepseek":
        assert float(chat_model.request_timeout) == 60
