# -*- coding: utf-8 -*-
"""workspace_assistant 的 LangGraph 工作流：文档问答 / 学习笔记 / 跨语言 / 内容草稿。"""
from __future__ import annotations

import json
import re
import uuid
from typing import TypedDict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.graph import END, START, StateGraph

from core.llm.factory import chat_model

REFUSAL = "资料中没有找到足够信息，无法确定。"


class WorkspaceState(TypedDict, total=False):
    input: str
    query: str
    docs: list[dict]
    sources: list[str]
    answer: str
    outline: str
    draft: str
    notes: str
    language: str
    verified: str


def _invoke_tool(scenario, name: str, args: dict):
    tool = scenario.get_tool(name)
    return tool.invoke({
        "name": name,
        "args": args,
        "id": f"workspace-{uuid.uuid4().hex}",
        "type": "tool_call",
    })


def _payload(result) -> dict:
    content = getattr(result, "content", result)
    if isinstance(content, list):
        content = "".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    try:
        data = json.loads(str(content))
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _search(scenario, query: str, limit: int = 5) -> list[dict]:
    data = _payload(_invoke_tool(scenario, "search_notes", {"query": query, "limit": limit}))
    results = data.get("results")
    results = [item for item in results if isinstance(item, dict)] if isinstance(results, list) else []
    # 笔记很短，直接读前两条全文，避免摘要片段丢失关键内容。
    for item in results[:2]:
        note = _payload(_invoke_tool(scenario, "read_note", {"note_id": item.get("id")}))
        if note.get("ok"):
            item["content"] = note.get("content", "")
    return results


def _context(results: list[dict]) -> str:
    lines = []
    for item in results:
        body = str(item.get("content") or item.get("snippet") or "")[:2000]
        lines.append(
            f"[{item.get('id')}] {item.get('title')} ({item.get('source')})\n{body}"
        )
    return "\n\n".join(lines)


def _has_citation(answer: str, results: list[dict]) -> bool:
    if not results:
        return False
    for item in results:
        if str(item.get("id")) in answer or str(item.get("title")) in answer:
            return True
    return False


_ANSWER_CHAIN = (
    PromptTemplate.from_template(
        "你是办公/学习助手。只根据资料回答问题，必须用 [笔记id] 标注来源；"
        "资料不足时输出“{refusal}”。\n\n资料：\n{context}\n\n问题：{query}"
    )
    | chat_model
    | StrOutputParser()
)

_OUTLINE_CHAIN = (
    PromptTemplate.from_template(
        "根据资料为主题写一个学习笔记大纲，列出 3-6 个章节，每章 1-3 个要点。\n"
        "主题：{query}\n资料：\n{context}"
    )
    | chat_model
    | StrOutputParser()
)

_NOTES_CHAIN = (
    PromptTemplate.from_template(
        "把下面的资料写成一份 Markdown 学习笔记，包含：关键概念、要点、术语、3 个复习问题。"
        "引用来源使用 [笔记id]。\n主题：{query}\n大纲：{outline}\n资料：\n{context}"
    )
    | chat_model
    | StrOutputParser()
)

_CROSS_CHAIN = (
    PromptTemplate.from_template(
        "用{language}回答用户问题，必须引用资料 [笔记id]；资料不足时明确说无法确定。\n"
        "资料：\n{context}\n\n问题：{query}"
    )
    | chat_model
    | StrOutputParser()
)

_DRAFT_OUTLINE_CHAIN = (
    PromptTemplate.from_template("为主题写一个内容大纲，3-5 个部分，每部分一句说明。\n主题：{query}")
    | chat_model
    | StrOutputParser()
)

_DRAFT_CHAIN = (
    PromptTemplate.from_template("根据大纲写一段完整内容，语气专业、面向普通读者。\n主题：{query}\n大纲：{outline}")
    | chat_model
    | StrOutputParser()
)

_REVIEW_CHAIN = (
    PromptTemplate.from_template("检查下面内容的事实一致性、结构和语气，输出修订后的最终版本。\n内容：{draft}")
    | chat_model
    | StrOutputParser()
)


def _detect_language(text: str) -> str:
    return "中文" if re.search(r"[一-鿿]", text or "") else "English"


def build_graphs(scenario) -> dict:
    graphs = {}

    # 1. document_qa: 检索 → 回答 → 引用检查
    qa = StateGraph(WorkspaceState)

    def qa_retrieve(state: WorkspaceState):
        results = _search(scenario, state["input"])
        return {"query": state["input"], "docs": results, "sources": [item["id"] for item in results]}

    def qa_answer(state: WorkspaceState):
        answer = _ANSWER_CHAIN.invoke({
            "refusal": REFUSAL,
            "context": _context(state.get("docs", [])),
            "query": state["input"],
        })
        return {"answer": answer}

    def qa_refuse(_state: WorkspaceState):
        return {"answer": REFUSAL, "verified": "refused"}

    def qa_cite(state: WorkspaceState):
        answer = state.get("answer", "")
        if not _has_citation(answer, state.get("docs", [])):
            sources = "、".join(f"[{item['id']}] {item['title']}" for item in state.get("docs", []))
            answer = f"{answer}\n\n来源：{sources}"
        return {"answer": answer, "verified": "cited"}

    qa.add_node("retrieve", qa_retrieve)
    qa.add_node("answer", qa_answer)
    qa.add_node("refuse", qa_refuse)
    qa.add_node("cite", qa_cite)
    qa.add_edge(START, "retrieve")
    qa.add_conditional_edges("retrieve", lambda state: "answer" if state.get("docs") else "refuse", {
        "answer": "answer",
        "refuse": "refuse",
    })
    qa.add_edge("answer", "cite")
    qa.add_edge("cite", END)
    qa.add_edge("refuse", END)
    graphs["document_qa"] = qa.compile()

    # 2. study_notes: 检索 → 大纲 → 笔记
    notes = StateGraph(WorkspaceState)

    def notes_retrieve(state: WorkspaceState):
        results = _search(scenario, state["input"])
        return {"query": state["input"], "docs": results, "sources": [item["id"] for item in results]}

    def notes_outline(state: WorkspaceState):
        return {
            "outline": _OUTLINE_CHAIN.invoke({
                "query": state["input"],
                "context": _context(state.get("docs", [])),
            })
        }

    def notes_write(state: WorkspaceState):
        return {
            "notes": _NOTES_CHAIN.invoke({
                "query": state["input"],
                "outline": state.get("outline", ""),
                "context": _context(state.get("docs", [])),
            })
        }

    def notes_refuse(_state: WorkspaceState):
        return {"notes": REFUSAL, "verified": "refused"}

    notes.add_node("retrieve", notes_retrieve)
    notes.add_node("outline", notes_outline)
    notes.add_node("write", notes_write)
    notes.add_node("refuse", notes_refuse)
    notes.add_edge(START, "retrieve")
    notes.add_conditional_edges("retrieve", lambda state: "outline" if state.get("docs") else "refuse", {
        "outline": "outline",
        "refuse": "refuse",
    })
    notes.add_edge("outline", "write")
    notes.add_edge("write", END)
    notes.add_edge("refuse", END)
    graphs["study_notes"] = notes.compile()

    # 3. cross_lingual: 语言检测 → 检索 → 同语言回答
    cross = StateGraph(WorkspaceState)

    def cross_detect(state: WorkspaceState):
        return {"query": state["input"], "language": _detect_language(state["input"])}

    def cross_retrieve(state: WorkspaceState):
        results = _search(scenario, state["input"])
        return {"docs": results, "sources": [item["id"] for item in results]}

    def cross_answer(state: WorkspaceState):
        return {
            "answer": _CROSS_CHAIN.invoke({
                "language": state.get("language", "中文"),
                "context": _context(state.get("docs", [])),
                "query": state["input"],
            })
        }

    def cross_refuse(_state: WorkspaceState):
        return {"answer": REFUSAL, "verified": "refused"}

    cross.add_node("detect", cross_detect)
    cross.add_node("retrieve", cross_retrieve)
    cross.add_node("answer", cross_answer)
    cross.add_node("refuse", cross_refuse)
    cross.add_edge(START, "detect")
    cross.add_edge("detect", "retrieve")
    cross.add_conditional_edges("retrieve", lambda state: "answer" if state.get("docs") else "refuse", {
        "answer": "answer",
        "refuse": "refuse",
    })
    cross.add_edge("answer", END)
    cross.add_edge("refuse", END)
    graphs["cross_lingual"] = cross.compile()

    # 4. content_draft: 大纲 → 草稿 → 审阅
    draft = StateGraph(WorkspaceState)

    def draft_outline(state: WorkspaceState):
        return {"query": state["input"], "outline": _DRAFT_OUTLINE_CHAIN.invoke({"query": state["input"]})}

    def draft_write(state: WorkspaceState):
        return {
            "draft": _DRAFT_CHAIN.invoke({
                "query": state["input"],
                "outline": state.get("outline", ""),
            })
        }

    def draft_review(state: WorkspaceState):
        return {"answer": _REVIEW_CHAIN.invoke({"draft": state.get("draft", "")})}

    draft.add_node("outline", draft_outline)
    draft.add_node("write", draft_write)
    draft.add_node("review", draft_review)
    draft.add_edge(START, "outline")
    draft.add_edge("outline", "write")
    draft.add_edge("write", "review")
    draft.add_edge("review", END)
    graphs["content_draft"] = draft.compile()

    return graphs
