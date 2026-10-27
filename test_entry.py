# -*- coding: utf-8 -*-
"""Agent Harness 统一测试入口。

用法：
    python test_entry.py --list
    python test_entry.py --all
    python test_entry.py --case agent-rag-001
    python test_entry.py --interactive
    python test_entry.py --all --judge
    python test_entry.py --scenario robot_vacuum --limit 3

RAG/LLM 评测：
    python test_entry.py rag retrieval
    python test_entry.py rag generation
    python test_entry.py rag judge
    python test_entry.py benchmark public

工作流：
    python test_entry.py workflow --list
    python test_entry.py workflow --run rag_qa --input "..."
    python test_entry.py workflow --run report --input "生成我的使用报告"
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from scenarios.registry import list_scenarios  # noqa: E402
from tests import runner  # noqa: E402


def main():
    # BFCL 工具调用评测
    if len(sys.argv) > 1 and sys.argv[1] == "bfcl":
        result = subprocess.run(
            [sys.executable, str(ROOT / "evals" / "run_eval.py"), "bfcl", *sys.argv[2:]],
            cwd=str(ROOT),
        )
        raise SystemExit(result.returncode)

    # LangGraph 工作流入口
    if len(sys.argv) > 1 and sys.argv[1] == "workflow":
        from agent.workflow import main as workflow_main
        workflow_main(sys.argv[2:])
        return

    # RAG/LLM 评测统一转发到 evals/run_eval.py
    if len(sys.argv) > 1 and sys.argv[1] in {"rag", "benchmark"}:
        group = sys.argv[1]
        rest = sys.argv[2:]
        valid = {"retrieval", "generation", "judge"} if group == "rag" else {"public"}
        if not rest or rest[0] not in valid:
            print(f"{group} 可用命令：{', '.join(sorted(valid))}")
            return
        command, extra = rest[0], rest[1:]
        result = subprocess.run(
            [sys.executable, str(ROOT / "evals" / "run_eval.py"), command, *extra],
            cwd=str(ROOT),
        )
        raise SystemExit(result.returncode)

    parser = argparse.ArgumentParser(description="ReAct Agent 测试入口")
    parser.add_argument("--scenario", default="robot_vacuum", help="场景名，默认 robot_vacuum")
    parser.add_argument("--all", action="store_true", help="跑全部用例（默认行为）")
    parser.add_argument("--case", help="只跑指定用例 ID")
    parser.add_argument("--list", action="store_true", help="列出场景和用例")
    parser.add_argument("--interactive", action="store_true", help="交互式对话测试")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 条用例")
    parser.add_argument("--judge", action="store_true", help="启用 LLM-as-judge 复核")
    args = parser.parse_args()

    if args.list:
        print("可用场景：" + ", ".join(list_scenarios()))
        try:
            runner.list_cases(args.scenario)
        except Exception as exc:  # noqa: BLE001
            print(f"加载场景 {args.scenario} 失败：{exc}")
        return

    if args.interactive:
        runner.interactive(args.scenario)
        return

    if args.case:
        runner.run(args.scenario, case_id=args.case, judge=args.judge)
    else:
        runner.run(args.scenario, limit=args.limit, judge=args.judge)


if __name__ == "__main__":
    main()
