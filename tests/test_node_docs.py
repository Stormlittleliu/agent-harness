# -*- coding: utf-8 -*-
"""节点说明 + trace 节点归因：调用链要能说清"这一步是哪个节点做的"。"""
import json
from typing import TypedDict

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph

from core.observability.tracer import TraceCallbackHandler
from core.scenarios.node_docs import describe_node, node_label, node_docs
from core.scenarios.registry import get_scenario


class State(TypedDict, total=False):
    answer: str
    files: str


@tool("list_notes")
def list_notes() -> str:
    """列出笔记。"""
    return "- note1"


def _graph(model) -> object:
    graph = StateGraph(State)

    def answer(state: State) -> dict:
        reply = model.invoke([("human", "hi")])
        return {"answer": reply.content}

    def verify(state: State) -> dict:
        result = list_notes.invoke({"name": "list_notes", "args": {}, "id": "t1", "type": "tool_call"})
        return {"files": getattr(result, "content", str(result))}

    graph.add_node("answer", answer)
    graph.add_node("verify", verify)
    graph.add_edge(START, "answer")
    graph.add_edge("answer", "verify")
    graph.add_edge("verify", END)
    return graph.compile()


def _events(tmp_path, graph) -> list[dict]:
    model = GenericFakeChatModel(messages=iter([AIMessage(content="ok")]))
    tracer = TraceCallbackHandler(trace_id="t-1", thread_id="th", scenario="demo_scene")
    tracer._trace_dir = tmp_path
    graph.invoke({"answer": ""}, config={"callbacks": [tracer], "metadata": {"x": 1}})
    tracer.finalize()
    rows: list[dict] = []
    for path in tmp_path.glob("*.jsonl"):
        rows.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    return rows


def test_model_events_carry_langgraph_node(tmp_path):
    graph = _graph(GenericFakeChatModel(messages=iter([AIMessage(content="ok")])))
    rows = _events(tmp_path, graph)
    model_rows = [row for row in rows if row["event"] == "model_end"]
    assert [row["node"] for row in model_rows] == ["answer"]


def test_tool_events_carry_langgraph_node(tmp_path):
    graph = _graph(GenericFakeChatModel(messages=iter([AIMessage(content="ok")])))
    rows = _events(tmp_path, graph)
    tool_rows = [row for row in rows if row["event"] in {"tool_start", "tool_end"}]
    assert tool_rows, "工具事件没有写进 trace"
    assert {row["node"] for row in tool_rows} == {"verify"}
    assert all(row["tool"] == "list_notes" for row in tool_rows)


def test_code_scenario_node_docs():
    doc = describe_node("robot_vacuum", "verify")
    assert doc is not None
    assert doc.label == "复核"
    assert "资料" in doc.desc
    assert node_label("robot_vacuum", "verify").startswith("复核")


def test_spec_scenario_node_docs_come_from_blocks():
    doc = describe_node("flow_demo", "verify")
    assert doc is not None
    assert doc.label == "引用校验"
    assert "[来源id]" in doc.desc


def test_unknown_node_falls_back_to_raw_name():
    assert describe_node("robot_vacuum", "no_such_node") is None
    assert node_label("robot_vacuum", "no_such_node") == "no_such_node"


@pytest.mark.parametrize(
    "name",
    ["robot_vacuum", "workspace_assistant", "research_assistant", "flow_demo"],
)
def test_every_workflow_node_has_doc(name):
    """每个编译出来的节点都必须有说明：新增节点忘了写文档，这里会红。"""
    scenario = get_scenario(name)
    graphs = scenario.workflow_factory(scenario)
    missing = []
    for graph_name, compiled in graphs.items():
        for node in compiled.get_graph().nodes:
            if node in {"__start__", "__end__"}:
                continue
            if describe_node(name, node, graph_name) is None:
                missing.append(f"{graph_name}.{node}")
    assert not missing, f"{name} 缺节点说明：{missing}"


def test_node_docs_registry_is_shared():
    docs = node_docs("workspace_assistant")
    assert {"retrieve", "answer", "refuse", "cite", "outline", "write", "detect", "review"} <= set(docs)
