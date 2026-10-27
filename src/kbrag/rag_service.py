"""RAG 聊天链：检索 -> Prompt -> LLM -> 输出，并带文件会话历史。"""
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import (
    RunnableLambda,
    RunnablePassthrough,
    RunnableWithMessageHistory,
)

from kbrag.history import get_history
from kbrag.prompts import CHAT_SYSTEM_TEMPLATE, HISTORY_SYSTEM_TEMPLATE, format_docs
from kbrag.providers import get_chat_model
from kbrag.retrievers import get_retriever


class RagService(object):
    def __init__(self):
        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                ("system", CHAT_SYSTEM_TEMPLATE),
                ("system", HISTORY_SYSTEM_TEMPLATE),
                MessagesPlaceholder("history"),
                ("user", "请回答用户提问：{input}"),
            ]
        )

        self.chat_model = get_chat_model()

        self.chain = self.__get_chain()

    def __get_chain(self):
        """获取最终的执行链"""

        # 默认检索模式来自 config/rag.yml（vector / hybrid）
        retriever = get_retriever()

        def format_for_retriever(value: dict) -> str:
            return value["input"]

        def format_for_prompt_template(value):
            # {input, context, history}
            return {
                "input": value["input"]["input"],
                "context": value["context"],
                "history": value["input"]["history"],
            }

        chain = (
            {
                "input": RunnablePassthrough(),
                "context": RunnableLambda(format_for_retriever) | retriever | format_docs,
            }
            | RunnableLambda(format_for_prompt_template)
            | self.prompt_template
            | self.chat_model
            | StrOutputParser()
        )

        conversation_chain = RunnableWithMessageHistory(  # 增强的链
            chain,
            get_history,
            input_messages_key="input",
            history_messages_key="history",
        )

        return conversation_chain


if __name__ == "__main__":
    import uuid

    # 每次命令行运行使用独立会话，避免和其他用户的历史混在一起
    session_id = f"cli_{uuid.uuid4().hex[:8]}"
    session_config = {
        "configurable": {
            "session_id": session_id,
        }
    }
    print(f"会话 ID: {session_id}")
    res = RagService().chain.invoke({"input": "我之前问了什么"}, session_config)
    print(res)
