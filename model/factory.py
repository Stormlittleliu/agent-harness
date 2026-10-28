import os
from abc import ABC, abstractmethod
from typing import Optional

from langchain_community.chat_models.tongyi import BaseChatModel, ChatTongyi

from utils.config_handler import rag_conf

from dotenv import load_dotenv
load_dotenv()


class BaseModelFactory(ABC):
    @abstractmethod
    def generator(self) -> Optional[BaseChatModel]:
        pass


class ChatModelFactory(BaseModelFactory):
    def generator(self) -> Optional[BaseChatModel]:
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


chat_model = ChatModelFactory().generator()
