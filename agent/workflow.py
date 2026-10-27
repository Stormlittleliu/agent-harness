# -*- coding: utf-8 -*-
"""基于 LangGraph 的可配置工作流引擎。

工作流用 YAML 定义（config/workflows/*.yml），节点类型：
- rag_retrieve：检索知识库，写入 context
- rag_answer：基于 context 生成回答，写入 answer
- llm：PromptTemplate + chat_model，写入指定字段
- tool：调用场景注册的工具，参数支持 {state_key} 模板
- router：按字段关键词分流（条件边）

新增工作流只需要在 config/workflows/ 下加一个 YAML，不需要改框架代码。
"""
import argparse
import json
import sys
from pathlib import Path
from typing import TypedDict

import yaml
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langgraph.graph import END, START, StateGraph

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model.factory import chat_model  # noqa: E402
from rag.rag_service import RagSummarizeService  # noqa: E402
from scenarios.registry import get_scenario  # noqa: E402

WORKFLOWS_DIR = ROOT / "config" / "workflows"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


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
    route: str


def list_workflows():
    workflows = []
    for path in sorted(WORKFLOWS_DIR.glob("*.yml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        workflows.append({
            "name": spec.get("name", path.stem),
            "description": spec.get("description", ""),
            "path": path,
        })
    return workflows


def load_workflow(name: str):
    path = WORKFLOWS_DIR / f"{name}.yml"
    if not path.exists():
        available = ", ".join(item["name"] for item in list_workflows())
        raise FileNotFoundError(f"工作流不存在：{name}（可用：{available}）")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


class WorkflowEngine:
    def __init__(self, scenario_name: str = "robot_vacuum"):
        self.scenario = get_scenario(scenario_name)
        self.tools = {tool.name: tool for tool in self.scenario.tools}
        self.rag = RagSummarizeService()
        self.chat_model = chat_model

    # ===================== 节点实现 =====================
    def _rag_retrieve(self, node):
        def run(state):
            docs = self.rag.retriever_docs(state["input"])
            return {
                "context": "\n\n".join(doc.page_content for doc in docs),
                "retrieved_sources": [str((doc.metadata or {}).get("source", "")) for doc in docs],
            }
        return run

    def _rag_answer(self, node):
        output_key = node.get("output", "answer")

        def run(state):
            answer = self.rag.chain.invoke({
                "input": state["input"],
                "context": state.get("context", ""),
            })
            return {output_key: answer}
        return run

    def _llm(self, node):
        output_key = node.get("output", "answer")
        chain = PromptTemplate.from_template(node["prompt"]) | self.chat_model | StrOutputParser()

        def run(state):
            return {output_key: chain.invoke(dict(state))}
        return run

    def _tool(self, node):
        tool_name = node["tool"]
        if tool_name not in self.tools:
            raise ValueError(f"工作流引用了未注册工具：{tool_name}")
        output_key = node.get("output", "result")
        tool = self.tools[tool_name]

        def run(state):
            args = {
                key: value.format(**state) if isinstance(value, str) else value
                for key, value in (node.get("args") or {}).items()
            }
            return {output_key: tool.invoke(args)}
        return run

    @staticmethod
    def _router(node):
        def run(state):
            return {}

        def route(state):
            text = str(state.get(node.get("field", ""), ""))
            routes = node.get("routes", [])
            for item in routes:
                if item.get("default"):
                    continue
                if any(keyword in text for keyword in item.get("if_contains", [])):
                    return item["target"]
            for item in routes:
                if item.get("default"):
                    return item.get("target") or item["default"]
            return "end"
        return run, route

    # ===================== 图构建 =====================
    def build(self, spec):
        graph = StateGraph(WorkflowState)
        nodes = spec.get("nodes", {})
        routers = {}

        for name, node in nodes.items():
            node_type = node.get("type")
            if node_type == "rag_retrieve":
                graph.add_node(name, self._rag_retrieve(node))
            elif node_type == "rag_answer":
                graph.add_node(name, self._rag_answer(node))
            elif node_type == "llm":
                graph.add_node(name, self._llm(node))
            elif node_type == "tool":
                graph.add_node(name, self._tool(node))
            elif node_type == "router":
                run, route = self._router(node)
                graph.add_node(name, run)
                routers[name] = route
            else:
                raise ValueError(f"未知节点类型：{node_type}（节点 {name}）")

        entry = spec.get("entry")
        if entry not in nodes:
            raise ValueError(f"工作流入口不存在：{entry}")
        graph.add_edge(START, entry)

        for name, node in nodes.items():
            targets = []
            if node.get("type") == "router":
                targets = [
                    item.get("target") or item.get("default")
                    for item in node.get("routes", [])
                ]
                if any(target is None for target in targets):
                    raise ValueError(f"路由缺少 target/default：{name}")
                for target in targets:
                    if target != "end" and target not in nodes:
                        raise ValueError(f"路由目标不存在：{target}")
                graph.add_conditional_edges(
                    name,
                    routers[name],
                    {target: (END if target == "end" else target) for target in set(targets)},
                )
            else:
                target = node.get("next", "end")
                if target != "end" and target not in nodes:
                    raise ValueError(f"next 目标不存在：{target}")
                graph.add_edge(name, END if target == "end" else target)

        return graph.compile()

    def run(self, name: str, input_text: str):
        spec = load_workflow(name)
        graph = self.build(spec)
        return graph.invoke({"input": input_text})


def _print_result(state: dict):
    for key in ("answer", "verified", "report"):
        if state.get(key):
            print(f"\n[{key}]\n{state[key]}")
    if not any(state.get(key) for key in ("answer", "verified", "report")):
        print(json.dumps(state, ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description="LangGraph 工作流引擎")
    parser.add_argument("--list", action="store_true", help="列出工作流")
    parser.add_argument("--run", help="运行指定工作流")
    parser.add_argument("--input", default="", help="工作流输入")
    parser.add_argument("--scenario", default="robot_vacuum")
    parser.add_argument("--show-state", action="store_true", help="打印完整 state")
    parser.add_argument("--dry-run", action="store_true", help="只编译工作流，不调用模型")
    args = parser.parse_args(argv)

    if args.list or not args.run:
        print("可用工作流：")
        for item in list_workflows():
            print(f"  {item['name']:<12} {item['description']}")
        return

    engine = WorkflowEngine(args.scenario)
    spec = load_workflow(args.run)
    graph = engine.build(spec)
    if args.dry_run:
        print(f"工作流 {args.run} 编译通过：{', '.join(spec.get('nodes', {}))}")
        return

    state = graph.invoke({"input": args.input})
    _print_result(state)
    if args.show_state:
        print("\n=== state ===")
        print(json.dumps(state, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
