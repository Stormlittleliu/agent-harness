"""
总结服务类：用户提问，搜索参考资料，将提问和参考资料提交给模型，让模型总结回复。

检索器由 rag/retrievers.py 按 config/rag.yml 的 retrieval_mode 创建：
默认 hybrid（向量 + BM25 关键词兜底），也可切换为 vector。
"""
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from model.factory import chat_model
from rag.retrievers import get_retriever
from utils.prompt_loader import load_rag_prompts


class RagSummarizeService:
    def __init__(self, retrieval_mode: str = None):
        self.retriever = get_retriever(retrieval_mode)
        self.prompt_text = load_rag_prompts()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self._init_chain()

    def _init_chain(self):
        return self.prompt_template | self.model | StrOutputParser()

    def retriever_docs(self, query: str) -> list[Document]:
        return self.retriever.invoke(query)

    def rag_summarize(self, query: str) -> str:
        context_docs = self.retriever_docs(query)

        context = ""
        counter = 0
        for doc in context_docs:
            counter += 1
            context += f"【参考资料{counter}】: 参考资料：{doc.page_content} | 参考元数据：{doc.metadata}\n"

        return self.chain.invoke(
            {
                "input": query,
                "context": context,
            }
        )


if __name__ == '__main__':
    rag = RagSummarizeService()

    print(rag.rag_summarize("小户型适合哪些扫地机器人"))
