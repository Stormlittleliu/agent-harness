# -*- coding: utf-8 -*-
"""research_assistant 的 LangGraph 工作流：规划 → 只读 fan-out → 汇总 → 引用 → 报告。"""
from __future__ import annotations

import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TypedDict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.graph import END, START, StateGraph

from core.llm.factory import chat_model
from core.scenarios.node_docs import NodeDoc, register_node_docs

NODE_DOCS = (
    NodeDoc("plan", "拆子问题", "把研究问题拆成最多 3 个能独立回答的子问题", "deep_research"),
    NodeDoc("fan_out", "并跑子 Agent", "用 subagent 并发读资料回答每个子问题，单点失败不影响整体", "deep_research"),
    NodeDoc("synthesize", "汇总对比", "把子结论合成对比总结，指出一致点、差异点与仍不确定的地方", "deep_research"),
    NodeDoc("cite", "补来源", "总结里没有资料 id 时追加来源列表", "deep_research"),
    NodeDoc("report", "写报告", "把总结写进报告文件并返回路径", "deep_research"),
)
register_node_docs("research_assistant", NODE_DOCS)


class ResearchState(TypedDict, total=False):
    input: str
    queries: list[str]
    findings: list[dict]
    summary: str
    sources: list[str]
    report_path: str
    verified: str


def _invoke_tool(scenario, name: str, args: dict):
    tool = scenario.get_tool(name)
    return tool.invoke({
        "name": name,
        "args": args,
        "id": f"research-{uuid.uuid4().hex}",
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


_PLAN_CHAIN = (
    PromptTemplate.from_template(
        "把下面的研究问题拆成 3 个可以独立检索的子问题。每行一个，不要编号，不要解释。\n问题：{query}"
    )
    | chat_model
    | StrOutputParser()
)

_SYNTH_CHAIN = (
    PromptTemplate.from_template(
        "根据下面的多份子 Agent 结论，写一份对比总结，必须引用资料 id（如 source_a）。"
        "指出一致点、差异点和仍不确定的地方。\n\n"
        "子问题与结论：\n{findings}\n\n原始问题：{query}"
    )
    | chat_model
    | StrOutputParser()
)


def _plan_queries(state: ResearchState) -> dict:
    text = _PLAN_CHAIN.invoke({"query": state["input"]})
    queries = [line.strip(" -•\t") for line in text.splitlines() if line.strip(" -•\t")]
    return {"queries": queries[:3] or [state["input"]]}


def _run_one(scenario, query: str) -> str:
    try:
        tool = scenario.get_tool("subagent")
        return tool.invoke({
            "name": "subagent",
            "args": {
                "description": (
                    f"阅读研究资料并回答这个子问题：{query}。"
                    "只返回结论和引用的资料 id，不要改文件，不要继续委派。"
                )
            },
            "id": f"research-sub-{uuid.uuid4().hex}",
            "type": "tool_call",
        }).content
    except Exception as exc:  # noqa: BLE001
        return f"子 Agent 失败：{type(exc).__name__}: {exc}"


def _fan_out(scenario, state: ResearchState) -> dict:
    queries = state.get("queries") or [state["input"]]
    findings: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(3, len(queries))) as pool:
        futures = {pool.submit(_run_one, scenario, query): query for query in queries}
        for future in as_completed(futures):
            query = futures[future]
            try:
                content = future.result()
            except Exception as exc:  # noqa: BLE001
                content = f"子 Agent 失败：{type(exc).__name__}: {exc}"
            findings.append({"query": query, "result": str(content)})
    findings.sort(key=lambda item: item["query"])
    return {"findings": findings}


def _synthesize(state: ResearchState) -> dict:
    findings = "\n\n".join(
        f"子问题：{item['query']}\n结论：{item['result']}" for item in state.get("findings", [])
    )
    summary = _SYNTH_CHAIN.invoke({"findings": findings, "query": state["input"]})
    return {"summary": summary}


def _cite(scenario, state: ResearchState) -> dict:
    summary = state.get("summary", "")
    data = _payload(_invoke_tool(scenario, "list_sources", {}))
    source_ids = [item.get("id") for item in data.get("sources", []) if isinstance(item, dict)]
    source_ids = [str(item) for item in source_ids if item]
    if source_ids and not any(source_id in summary for source_id in source_ids):
        summary = f"{summary}\n\n来源：{', '.join(source_ids)}"
    return {"summary": summary, "sources": source_ids, "verified": "cited"}


def _write_report(scenario, state: ResearchState) -> dict:
    content = state.get("summary", "")
    data = _payload(_invoke_tool(
        scenario,
        "write_report",
        {"title": "研究对比报告", "content": content},
    ))
    return {"report_path": str(data.get("path") or ""), "summary": content}


def build_graphs(scenario) -> dict:
    graph = StateGraph(ResearchState)
    graph.add_node("plan", _plan_queries)
    graph.add_node("fan_out", lambda state: _fan_out(scenario, state))
    graph.add_node("synthesize", _synthesize)
    graph.add_node("cite", lambda state: _cite(scenario, state))
    graph.add_node("report", lambda state: _write_report(scenario, state))
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "fan_out")
    graph.add_edge("fan_out", "synthesize")
    graph.add_edge("synthesize", "cite")
    graph.add_edge("cite", "report")
    graph.add_edge("report", END)
    return {"deep_research": graph.compile()}
