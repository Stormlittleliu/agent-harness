"""Prompt 模板与上下文格式化，聊天页和对比页共用。

模板内容维护在 config/prompts.yml 中，改提示词不需要改代码。
"""
from langchain_core.documents import Document

from kbrag import config

# 聊天页：结合参考资料回答
CHAT_SYSTEM_TEMPLATE = config.chat_system_template
# 聊天页：说明接下来是历史消息
HISTORY_SYSTEM_TEMPLATE = config.history_system_template
# 对比页：纯模型回答（不使用知识库）
PLAIN_SYSTEM_TEMPLATE = config.plain_system_template
# 对比页：RAG 回答（使用知识库）
RAG_SYSTEM_TEMPLATE = config.rag_system_template


def format_docs(docs: list[Document]) -> str:
    """把检索到的文档拼接成上下文；没有检索结果时给出明确提示。"""
    if not docs:
        return "无相关参考资料"
    return "\n\n".join(doc.page_content for doc in docs)
