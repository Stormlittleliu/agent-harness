import os
from abc import ABC, abstractmethod
from typing import Optional
from langchain_core.embeddings import Embeddings
from langchain_community.chat_models.tongyi import BaseChatModel
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.chat_models.tongyi import ChatTongyi
from utils.config_handler import rag_conf

from dotenv import load_dotenv
load_dotenv()


class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        pass


class LazyLocalEmbeddings(Embeddings):
    """延迟初始化本地 sentence-transformers 模型，避免 import 阶段就加载权重。"""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._impl = None

    def _get_impl(self):
        if self._impl is None:
            from pathlib import Path

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


class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        provider = str(rag_conf.get("chat_provider", "dashscope")).lower()

        if provider == "deepseek":
            from langchain_openai import ChatOpenAI
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                raise RuntimeError("缺少 DEEPSEEK_API_KEY，请在项目根目录 .env 中配置")
            return ChatOpenAI(
                model=rag_conf["chat_model_name"],
                base_url=rag_conf.get("chat_base_url", "https://api.deepseek.com"),
                api_key=api_key,
                temperature=float(rag_conf.get("chat_temperature", 0)),
            )

        return ChatTongyi(model=rag_conf["chat_model_name"], temperature=0)


class EmbeddingsFactory(BaseModelFactory):
    def generator(self) -> Optional[Embeddings | BaseChatModel]:
        provider = str(rag_conf.get("embedding_provider", "dashscope")).lower()

        if provider == "local":
            return LazyLocalEmbeddings(rag_conf["embedding_model_name"])

        return DashScopeEmbeddings(model=rag_conf["embedding_model_name"])


chat_model = ChatModelFactory().generator()

embed_model = EmbeddingsFactory().generator()
