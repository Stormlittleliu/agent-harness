# -*- coding: utf-8 -*-
"""通用工作流运行时：只执行 Scenario 提供的 LangGraph。

场景层（scenarios/<name>/graph.py）负责挑工具、定义节点和边；
本文件不知道任何业务工作流名，也不 import rag/business 工具。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


class WorkflowRuntime:
    def __init__(self, scenario):
        self.scenario = scenario
        factory = getattr(scenario, "workflow_factory", None)
        self.graphs = factory(scenario) if factory else {}

    def list_workflows(self) -> list[str]:
        return sorted(self.graphs)

    def run(self, name: str, input_text: str):
        if name not in self.graphs:
            available = ", ".join(self.list_workflows()) or "（无）"
            raise FileNotFoundError(f"工作流不存在：{name}（可用：{available}）")
        return self.graphs[name].invoke({"input": input_text})


def _print_result(state: dict):
    for key in ("answer", "verified", "report"):
        if state.get(key):
            print(f"\n[{key}]\n{state[key]}")
    if not any(state.get(key) for key in ("answer", "verified", "report")):
        print(json.dumps(state, ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description="LangGraph 工作流运行时")
    parser.add_argument("--scenario", default="robot_vacuum")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--run")
    parser.add_argument("--input", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    from scenarios.registry import get_scenario

    runtime = WorkflowRuntime(get_scenario(args.scenario))
    if args.list or not args.run:
        print("可用工作流：" + ", ".join(runtime.list_workflows()))
        return
    if args.dry_run:
        print(f"工作流 {args.run} 编译通过：{', '.join(runtime.list_workflows())}")
        return

    _print_result(runtime.run(args.run, args.input))


if __name__ == "__main__":
    main()
