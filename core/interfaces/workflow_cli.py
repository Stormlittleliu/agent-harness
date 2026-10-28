# -*- coding: utf-8 -*-
"""工作流 CLI：解析参数、取场景、调用通用 WorkflowRuntime。"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.agent.workflow import WorkflowRuntime  # noqa: E402
from core.scenarios.registry import get_scenario  # noqa: E402


def _print_result(state: dict) -> None:
    for key in ("answer", "verified", "report"):
        if state.get(key):
            print(f"\n[{key}]\n{state[key]}")
    if not any(state.get(key) for key in ("answer", "verified", "report")):
        print(json.dumps(state, ensure_ascii=False, indent=2))


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="LangGraph 工作流运行时")
    parser.add_argument("--scenario", default="robot_vacuum")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--run")
    parser.add_argument("--input", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

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
