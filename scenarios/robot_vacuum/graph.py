# -*- coding: utf-8 -*-
"""robot_vacuum 场景的 LangGraph 工作流。

场景层负责“挑哪些工具、怎么连边”；agent/ 只提供通用执行器。
"""
from __future__ import annotations

import uuid
from typing import TypedDict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.graph import END, START, StateGraph

from model.factory import chat_model

REFUSAL_MARKERS = ("没有相关信息", "资料不足", "未提及", "无法确定")


class WorkflowState(TypedDict, total=False):
    input: str
    context: str
    retrieved_sources: list[str]
    answer: str
    verified: str
    user_id: str
    month: str
    records: str
    report: str


def _invoke_tool(scenario, name: str, args: dict):
    tool = scenario.get_tool(name)
    return tool.invoke({
        "name": name,
        "args": args,
        "id": f"workflow-{uuid.uuid4().hex}",
        "type": "tool_call",
    })


def _content(result) -> str:
    content = getattr(result, "content", result)
    if isinstance(content, list):
        return "".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content)


def _docs(result) -> list[dict]:
    artifact = getattr(result, "artifact", None)
    return artifact.get("docs", []) if isinstance(artifact, dict) else []


def _context(docs: list[dict]) -> str:
    return "\n\n".join(str(item.get("content", "")) for item in docs)


def _sources(docs: list[dict]) -> list[str]:
    return [str(item.get("source", "")) for item in docs]


def _route_after_answer(state: WorkflowState) -> str:
    answer = state.get("answer", "")
    return "end" if any(marker in answer for marker in REFUSAL_MARKERS) else "verify"


def build_graphs(scenario) -> dict:
    """返回该场景的工作流：rag_qa / report。"""
    verify_chain = (
        PromptTemplate.from_template(
            "你是事实核查员。只根据下面资料判断回答是否有依据，不要使用外部知识。\n"
            "资料：{context}\n回答：{answer}\n只输出“有依据”或“无依据”。"
        )
        | chat_model
        | StrOutputParser()
    )
    report_chain = (
        PromptTemplate.from_template(
            "你是扫地机器人客服。根据以下使用记录，用中文写一份使用报告与保养建议。\n"
            "使用记录：{records}"
        )
        | chat_model
        | StrOutputParser()
    )

    # rag_qa：一次 rag_summarize（检索 + 总结）→ 拒答分流 → 引用校验
    rag_graph = StateGraph(WorkflowState)

    def rag_answer(state: WorkflowState):
        result = _invoke_tool(scenario, "rag_summarize", {"query": state["input"]})
        docs = _docs(result)
        return {
            "answer": _content(result),
            "context": _context(docs),
            "retrieved_sources": _sources(docs),
        }

    def verify(state: WorkflowState):
        return {"verified": verify_chain.invoke({
            "context": state.get("context", ""),
            "answer": state.get("answer", ""),
        })}

    rag_graph.add_node("answer", rag_answer)
    rag_graph.add_node("verify", verify)
    rag_graph.add_edge(START, "answer")
    rag_graph.add_conditional_edges("answer", _route_after_answer, {"end": END, "verify": "verify"})
    rag_graph.add_edge("verify", END)

    # report：用户 ID → 当前月份 → 使用记录 → 报告
    report_graph = StateGraph(WorkflowState)

    def get_user_id(_state: WorkflowState):
        return {"user_id": _content(_invoke_tool(scenario, "get_user_id", {}))}

    def get_current_month(_state: WorkflowState):
        return {"month": _content(_invoke_tool(scenario, "get_current_month", {}))}

    def fetch_records(state: WorkflowState):
        result = _invoke_tool(scenario, "fetch_external_data", {
            "user_id": state["user_id"],
            "month": state["month"],
        })
        return {"records": _content(result)}

    def write_report(state: WorkflowState):
        return {"report": report_chain.invoke({"records": state.get("records", "")})}

    report_graph.add_node("get_user_id", get_user_id)
    report_graph.add_node("get_current_month", get_current_month)
    report_graph.add_node("fetch_external_data", fetch_records)
    report_graph.add_node("write_report", write_report)
    report_graph.add_edge(START, "get_user_id")
    report_graph.add_edge("get_user_id", "get_current_month")
    report_graph.add_edge("get_current_month", "fetch_external_data")
    report_graph.add_edge("fetch_external_data", "write_report")
    report_graph.add_edge("write_report", END)

    return {"rag_qa": rag_graph.compile(), "report": report_graph.compile()}
