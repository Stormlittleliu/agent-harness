# -*- coding: utf-8 -*-
"""统一评测入口：能力层 + 行为层。

用法：
    python -m core.quality.runner agent --limit 2
    python -m core.quality.runner agent --case agent-rag-001 --judge
    python -m core.quality.runner rag retrieval --limit 5
    python -m core.quality.runner rag generation --mode hybrid --limit 5
    python -m core.quality.runner public --rgb-limit 2 --skip-multihop
    python -m core.quality.runner judge --input outputs/rag/eval_generation.json
    python -m core.quality.runner bfcl --simple 2 --irrelevance 2
    python -m core.quality.runner structured --limit 5
    python -m core.quality.runner failures
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.quality import agent_eval, bfcl_simplified as bfcl, failures, public_sample as public, rag_eval, rag_judge, structured_eval  # noqa: E402
from core.quality.paths import RAG_OUT  # noqa: E402


def _agent(args):
    if args.list:
        agent_eval.list_cases(args.scenario)
        return
    if args.interactive:
        agent_eval.interactive(args.scenario)
        return
    agent_eval.run(args.scenario, case_id=args.case, limit=args.limit, judge=args.judge)


def _rag(args):
    if args.rag_task == "retrieval":
        modes = tuple(item.strip() for item in args.modes.split(",") if item.strip())
        rag_eval.run_retrieval(
            dataset=args.dataset,
            docs_dir=args.docs_dir,
            modes=modes,
            k=args.k,
            limit=args.limit,
            out_dir=args.out_dir,
        )
    else:
        rag_eval.run_generation(
            dataset=args.dataset,
            docs_dir=args.docs_dir,
            mode=args.mode,
            k=args.k,
            limit=args.limit,
            out_dir=args.out_dir,
        )


def _public(args):
    benchmarks = tuple(item.strip() for item in args.benchmarks.split(",") if item.strip())
    if args.skip_multihop:
        benchmarks = tuple(item for item in benchmarks if item != "multihop")
    public.run(benchmarks, args.rgb_limit, args.multihop_limit)


def _judge(args):
    cmd = [
        "--input", args.input,
        "--prefix", args.prefix,
        "--limit", str(args.limit),
    ]
    if args.out_dir:
        cmd += ["--out-dir", args.out_dir]
    rag_judge.main(cmd)


def _bfcl(args):
    cmd = [
        "--simple", str(args.simple),
        "--irrelevance", str(args.irrelevance),
        "--delay", str(args.delay),
    ]
    if args.out_dir:
        cmd += ["--out-dir", args.out_dir]
    bfcl.main(cmd)


def _tau2(_args):
    print("τ²-bench 是外部官方 harness，不在本仓库内重写评分。")
    print(r"cd E:\CODE\benchmarks\tau2-bench")
    print(
        "python run_tau2_deepseek_judge.py run --domain retail "
        "--agent-llm deepseek/deepseek-chat --user-llm deepseek/deepseek-chat "
        "--num-tasks 20 --num-trials 1 --max-concurrency 2 --timeout 600 "
        "--save-to retail20_deepseek_judge"
    )
    print("结果由 python -m core.quality.runner failures 读取并归档。")


def build_parser():
    parser = argparse.ArgumentParser(description="Agent Harness 统一评测入口")
    sub = parser.add_subparsers(dest="command", required=True)

    p_agent = sub.add_parser("agent", help="行为层：ReactAgent 跑场景 cases")
    p_agent.add_argument("--scenario", default="robot_vacuum")
    p_agent.add_argument("--case")
    p_agent.add_argument("--limit", type=int, default=0)
    p_agent.add_argument("--judge", action="store_true")
    p_agent.add_argument("--list", action="store_true")
    p_agent.add_argument("--interactive", action="store_true")
    p_agent.set_defaults(func=_agent)

    p_rag = sub.add_parser("rag", help="能力层：invoke_tool 跑 RAG 检索/生成")
    rag_sub = p_rag.add_subparsers(dest="rag_task", required=True)

    p_ret = rag_sub.add_parser("retrieval")
    p_ret.add_argument("--dataset")
    p_ret.add_argument("--docs-dir")
    p_ret.add_argument("--modes", default="vector,hybrid")
    p_ret.add_argument("--k", type=int, default=4)
    p_ret.add_argument("--limit", type=int, default=0)
    p_ret.add_argument("--out-dir")

    p_gen = rag_sub.add_parser("generation")
    p_gen.add_argument("--dataset")
    p_gen.add_argument("--docs-dir")
    p_gen.add_argument("--mode", default="hybrid", choices=["vector", "hybrid"])
    p_gen.add_argument("--k", type=int, default=4)
    p_gen.add_argument("--limit", type=int, default=0)
    p_gen.add_argument("--out-dir")
    p_rag.set_defaults(func=_rag)

    p_public = sub.add_parser("public", help="能力层：RGB / MultiHop")
    p_public.add_argument("--benchmarks", default="rgb,multihop")
    p_public.add_argument("--rgb-limit", type=int, default=0)
    p_public.add_argument("--multihop-limit", type=int, default=0)
    p_public.add_argument("--skip-multihop", action="store_true")
    p_public.set_defaults(func=_public)

    p_judge = sub.add_parser("judge", help="RAG 生成结果 LLM judge")
    p_judge.add_argument("--input")
    p_judge.add_argument("--out-dir")
    p_judge.add_argument("--prefix", default="eval_generation")
    p_judge.add_argument("--limit", type=int, default=0)
    p_judge.set_defaults(func=_judge)

    p_bfcl = sub.add_parser("bfcl", help="BFCL 外部适配器")
    p_bfcl.add_argument("--simple", type=int, default=100)
    p_bfcl.add_argument("--irrelevance", type=int, default=100)
    p_bfcl.add_argument("--delay", type=float, default=0.2)
    p_bfcl.add_argument("--out-dir")
    p_bfcl.set_defaults(func=_bfcl)

    p_structured = sub.add_parser("structured", help="结构化输出评测：Pydantic schema")
    p_structured.add_argument("--scenario", default="structured_demo")
    p_structured.add_argument("--case")
    p_structured.add_argument("--limit", type=int, default=0)
    p_structured.add_argument("--out-dir")
    p_structured.set_defaults(
        func=lambda args: structured_eval.run(
            args.scenario, args.case, args.limit, args.out_dir
        )
    )

    p_fail = sub.add_parser("failures", help="归档失败集")
    p_fail.set_defaults(func=lambda _args: failures.main())

    p_tau2 = sub.add_parser("tau2", help="τ²-bench 外部命令说明")
    p_tau2.set_defaults(func=_tau2)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "input", None) is None and hasattr(args, "input"):
        args.input = str(RAG_OUT / "eval_generation.json")
    args.func(args)


if __name__ == "__main__":
    main()
