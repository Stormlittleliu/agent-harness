"""RAG 对比服务。

支持两种对比模式：
1. plain_vs_rag：同一个问题，纯模型（不使用知识库）vs RAG（检索知识库）；
2. vector_vs_hybrid：同一个问题，纯向量检索 vs 向量 + 关键词兜底混合检索，
   用于观察关键词兜底带来的召回差异。
"""
import json
import os
from datetime import datetime

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from kbrag import config
from kbrag.prompts import PLAIN_SYSTEM_TEMPLATE, RAG_SYSTEM_TEMPLATE, format_docs
from kbrag.providers import get_chat_model
from kbrag.retrievers import get_hybrid_retriever, get_retriever, get_vector_retriever

COMPARE_PATH = config.compare_history_path

# 两种对比模式的标识，页面层和记录文件共用
MODE_PLAIN_VS_RAG = "plain_vs_rag"
MODE_VECTOR_VS_HYBRID = "vector_vs_hybrid"


def load_records():
    """读取历史对比记录"""
    if not os.path.exists(COMPARE_PATH):
        return []
    try:
        with open(COMPARE_PATH, "r", encoding="utf-8") as f:
            records = json.load(f)
        return records if isinstance(records, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def save_records(records):
    """保存历史对比记录"""
    with open(COMPARE_PATH, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def _get_chains():
    model = get_chat_model()

    # 不使用知识库：不提供任何参考资料
    plain_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", PLAIN_SYSTEM_TEMPLATE),
            ("user", "请回答用户提问：{input}"),
        ]
    )

    # 使用知识库：和聊天页一样，把检索结果作为参考资料
    rag_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", RAG_SYSTEM_TEMPLATE),
            ("user", "请回答用户提问：{input}"),
        ]
    )

    return (
        plain_prompt | model | StrOutputParser(),
        rag_prompt | model | StrOutputParser(),
    )


def _format_sources(docs):
    """把检索结果整理成可序列化的参考资料列表（旧记录也兼容读取）。"""
    return [
        {
            "source": doc.metadata.get("source", "unknown"),
            "file_type": doc.metadata.get("file_type", ""),
            "content": doc.page_content.strip()[:300],
        }
        for doc in docs
    ]


def _run_plain_vs_rag(question, plain_chain, rag_chain):
    """模式一：纯模型 vs RAG（RAG 侧使用配置的默认检索模式）。"""
    retriever = get_retriever()

    plain_answer = plain_chain.invoke({"input": question})

    docs = retriever.invoke(question)
    context = format_docs(docs)
    rag_answer = rag_chain.invoke({"context": context, "input": question})

    return {
        "mode": MODE_PLAIN_VS_RAG,
        "question": question,
        "plain": plain_answer,
        "rag": rag_answer,
        "sources": _format_sources(docs),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": config.chat_model_name,
        "retrieval_k": config.retrieval_k,
        "retrieval_mode": config.retrieval_mode,
    }


def _run_vector_vs_hybrid(question, rag_chain):
    """模式二：纯向量检索 vs 向量 + 关键词兜底混合检索（同一个 Prompt 与模型）。"""
    vector_docs = get_vector_retriever().invoke(question)
    hybrid_docs = get_hybrid_retriever().invoke(question)

    vector_answer = rag_chain.invoke({"context": format_docs(vector_docs), "input": question})
    hybrid_answer = rag_chain.invoke({"context": format_docs(hybrid_docs), "input": question})

    return {
        "mode": MODE_VECTOR_VS_HYBRID,
        "question": question,
        "vector": vector_answer,
        "hybrid": hybrid_answer,
        "sources_vector": _format_sources(vector_docs),
        "sources_hybrid": _format_sources(hybrid_docs),
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model": config.chat_model_name,
        "retrieval_k": config.retrieval_k,
        "retrieval_mode": config.retrieval_mode,
        "hybrid_weights": config.hybrid_weights,
    }


def run_compare(question: str, mode: str = MODE_PLAIN_VS_RAG):
    """对一个问题执行指定模式的对比，返回一条可直接保存的记录。

    :param question: 用户问题
    :param mode: plain_vs_rag（纯模型 vs RAG）| vector_vs_hybrid（纯向量 vs 混合检索）
    """
    if mode not in (MODE_PLAIN_VS_RAG, MODE_VECTOR_VS_HYBRID):
        raise ValueError(f"未知的对比模式：{mode}")

    plain_chain, rag_chain = _get_chains()
    if mode == MODE_PLAIN_VS_RAG:
        return _run_plain_vs_rag(question, plain_chain, rag_chain)
    return _run_vector_vs_hybrid(question, rag_chain)
