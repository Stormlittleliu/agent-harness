# -*- coding: utf-8 -*-
"""最小 Harness 优化循环：跑 → 分类 badcase → 定向改 → 复跑 → 查回归。

用法：
    python -m core.experiments.optimize --iterations 5
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from core.experiments import bfcl_agent, rag_agent
from core.experiments.cases import load_bfcl_cases, load_multihop_cases, load_multihop_corpus

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parents[2]

BFCL_PLAIN = "你是一个工具调用助手。需要时调用提供的工具，然后回答用户。"
BFCL_STRICT = (
    "你是一个工具调用助手。必须调用且只调用一个提供的工具；"
    "参数名必须与 schema 完全一致，不要省略必填参数。"
)
BFCL_IRREL = (
    "你是一个工具调用助手。先判断问题是否需要调用工具；"
    "如果不需要，直接回答，不要调用任何工具。"
)
BFCL_PYTHON = (
    BFCL_STRICT
    + " 数学表达式必须使用 Python 语法：乘方写 **，不要写 ^；例如 2*x**2。"
)
RAG_PLAIN = "你是一个检索问答助手。需要资料时调用 rag_retrieve，然后基于资料回答。"
RAG_FORCE = "回答前必须先调用 rag_retrieve，使用用户原问题作为 query。不要直接凭记忆回答。"
RAG_MULTI = (
    "回答前先调用 rag_retrieve。对于比较、推理、时间类问题，调用多次，"
    "每次用不同的子问题；再综合所有资料回答。"
)

CONFIGS = [
    {
        "name": "baseline",
        "direction": "baseline",
        "knowledge_ref": "—",
        "change": "中性 prompt；vector k=4",
        "bfcl": BFCL_PLAIN, "rag": RAG_PLAIN, "retriever": "vector", "k": 4,
    },
    {
        "name": "routed_prompts",
        "direction": "A. Prompt routing",
        "knowledge_ref": "ReAct / tool-use prompting + 任务类型路由",
        "change": "simple 强制调用；irrelevance 先判断；comparison/inference 多子查询",
        "bfcl": BFCL_STRICT, "rag": RAG_FORCE, "retriever": "vector", "k": 4,
        "routing": True,
    },
    {
        "name": "hybrid",
        "direction": "C. Retrieval strategy (hybrid)",
        "knowledge_ref": "dense + BM25 hybrid retrieval",
        "change": "向量 + BM25 混合检索，k=8",
        "bfcl": BFCL_STRICT, "rag": RAG_FORCE, "retriever": "hybrid", "k": 8,
        "routing": True,
    },
    {
        "name": "english_embedding",
        "direction": "C. Retrieval strategy (English embedding)",
        "knowledge_ref": "跨语言检索：英文语料用英文 embedding",
        "change": "bge-small-en-v1.5 + vector k=8",
        "bfcl": BFCL_STRICT, "rag": RAG_FORCE, "retriever": "vector", "k": 8,
        "routing": True, "embedding": "en",
    },
    {
        "name": "arg_validation",
        "direction": "B. Tool design / E. Error handling",
        "knowledge_ref": "tool schema validation + error feedback",
        "change": "BFCL 必填参数校验中间件，缺参回注错误让模型重试",
        "bfcl": BFCL_STRICT, "rag": RAG_FORCE, "retriever": "vector", "k": 8,
        "routing": True, "embedding": "en", "validate_bfcl": True,
    },
    {
        "name": "python_syntax",
        "direction": "A. Tool description / prompt",
        "knowledge_ref": "tool-use prompting：明确参数语法",
        "change": "提示乘方使用 ** 而不是 ^",
        "bfcl": BFCL_PYTHON, "rag": RAG_FORCE, "retriever": "hybrid", "k": 8,
        "routing": True,
    },
    {
        "name": "bfcl_fixes",
        "direction": "A/B/E. Prompt + loop control",
        "knowledge_ref": "syntax hint + repeat tool-call suppression",
        "change": "Python 语法提示 + 同工具重复调用抑制",
        "bfcl": BFCL_PYTHON, "rag": RAG_FORCE, "retriever": "hybrid", "k": 8,
        "routing": True, "suppress_repeats": True,
    },
    {
        "name": "hybrid_validation",
        "direction": "B/E. Tool validation (isolated)",
        "knowledge_ref": "hybrid retrieval + schema validation",
        "change": "hybrid 基础上单独加参数校验",
        "bfcl": BFCL_STRICT, "rag": RAG_FORCE, "retriever": "hybrid", "k": 8,
        "routing": True, "validate_bfcl": True,
    },
]


def _aggregate(runs):
    passes = [bool(run["passed"]) for run in runs]
    first_failure = next((run for run in runs if not run["passed"]), None)
    result = dict(first_failure or runs[0])
    result["passed"] = all(passes)          # pass^k：k 次都成功
    result["pass_rate"] = sum(passes) / len(passes)
    result["trial_passes"] = passes
    return result


def _run_bfcl(cases, config, trials=1):
    validate_args = config.get("validate_bfcl", False)
    suppress_repeats = config.get("suppress_repeats", False)
    results = []
    for index, case in enumerate(cases, 1):
        prompt = config["bfcl"]
        if config.get("routing") and case["kind"] == "irrelevance":
            prompt = BFCL_IRREL
        runs = [
            bfcl_agent.run_case(
                case,
                prompt,
                validate_args=validate_args,
                suppress_repeats=suppress_repeats,
            )
            for _ in range(trials)
        ]
        result = _aggregate(runs)
        result["id"] = case["id"]
        result["kind"] = case["kind"]
        results.append(result)
        print(f"  [BFCL {index}/{len(cases)}] {result['id']} "
              f"pass^k={result['passed']} rate={result['pass_rate']:.0%} "
              f"{result['failure_type'] or 'pass'}")
    return results


def _run_rag(cases, corpus, config, trials=1):
    kind = config["retriever"]
    k = config["k"]
    embedding_name = config.get("embedding")
    if config.get("routing"):
        agents = {
            "multi": rag_agent.build_agent(
                corpus, RAG_MULTI, kind=kind, k=k, embedding_name=embedding_name
            ),
            "force": rag_agent.build_agent(
                corpus, RAG_FORCE, kind=kind, k=k, embedding_name=embedding_name
            ),
        }
    else:
        agents = {
            "default": rag_agent.build_agent(
                corpus, config["rag"], kind=kind, k=k, embedding_name=embedding_name
            )
        }

    results = []
    for index, case in enumerate(cases, 1):
        if config.get("routing"):
            key = "multi" if case["question_type"] in ("comparison_query", "inference_query") else "force"
        else:
            key = "default"
        agent = agents[key]
        runs = [rag_agent.run_case(agent, case) for _ in range(trials)]
        result = _aggregate(runs)
        result["id"] = case["id"]
        result["question_type"] = case["question_type"]
        results.append(result)
        print(f"  [RAG {index}/{len(cases)}] {result['question_type']} "
              f"pass^k={result['passed']} rate={result['pass_rate']:.0%} "
              f"{result['failure_type'] or 'pass'}")
    return results


def _summary(bfcl_results, rag_results):
    bfcl_by_kind = defaultdict(lambda: [0, 0])
    for row in bfcl_results:
        bfcl_by_kind[row["kind"]][1] += 1
        if row["passed"]:
            bfcl_by_kind[row["kind"]][0] += 1
    rag_by_type = defaultdict(lambda: [0, 0])
    for row in rag_results:
        rag_by_type[row["question_type"]][1] += 1
        if row["passed"]:
            rag_by_type[row["question_type"]][0] += 1
    return {
        "bfcl_pass": sum(1 for row in bfcl_results if row["passed"]),
        "bfcl_total": len(bfcl_results),
        "bfcl_mean": sum(row["pass_rate"] for row in bfcl_results) / max(len(bfcl_results), 1),
        "bfcl_by_kind": {key: f"{value[0]}/{value[1]}" for key, value in bfcl_by_kind.items()},
        "bfcl_failures": dict(Counter(row["failure_type"] for row in bfcl_results if not row["passed"])),
        "rag_pass": sum(1 for row in rag_results if row["passed"]),
        "rag_total": len(rag_results),
        "rag_mean": sum(row["pass_rate"] for row in rag_results) / max(len(rag_results), 1),
        "rag_hit4": sum(row["pass_rate"] for row in rag_results) / max(len(rag_results), 1),
        "rag_by_type": {key: f"{value[0]}/{value[1]}" for key, value in rag_by_type.items()},
        "rag_failures": dict(Counter(row["failure_type"] for row in rag_results if not row["passed"])),
    }


def _same_class(rows, failure_key="failure_type"):
    groups = defaultdict(lambda: [0, 0])
    for row in rows:
        key = row.get("kind") or row.get("question_type")
        groups[key][1] += 1
        if row["passed"]:
            groups[key][0] += 1
    return {key: f"{value[0]}/{value[1]}" for key, value in groups.items()}


def _compare(previous, current):
    if previous is None:
        return {"fixed": [], "regressed": [], "unchanged": []}
    prev = {row["id"]: row for row in previous if row.get("id")}
    fixed, regressed, unchanged = [], [], []
    for row in current:
        if not row.get("id"):
            continue
        old = prev.get(row["id"])
        if old is None:
            continue
        if not old["passed"] and row["passed"]:
            fixed.append(row["id"])
        elif old["passed"] and not row["passed"]:
            regressed.append(row["id"])
        else:
            unchanged.append(row["id"])
    return {"fixed": fixed, "regressed": regressed, "unchanged": unchanged}


def _write_report(out_dir, iterations, trials):
    lines = [
        "# 最小 Agent Harness 优化循环",
        "",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "- 模型：DeepSeek `deepseek-chat`",
        f"- 每个 case 跑 {trials} trial，主指标为 pass^k；括号内为平均通过率",
        "- BFCL：工具调用（simple + irrelevance），工具实现为 stub，评分看工具名/参数",
        "- MultiHop-RAG：609 篇语料，评分看是否召回 evidence title",
        "",
        "## 优化方向分类（参考公开 Agent 实践）",
        "",
        "| 方向 | 本轮 | 改动 | 公开参考 |",
        "|:---|:---:|:---|:---|",
        "| A. Prompt routing | Iter 2 | simple 强制调用；irrelevance 先判断 | ReAct / tool-use prompting |",
        "| D. Query planning | Iter 2 | comparison/inference 多子查询 | Self-Ask / RAG-Fusion |",
        "| C. Retrieval strategy | Iter 3/4 | hybrid BM25；英文 embedding | hybrid retrieval / cross-lingual |",
        "| B. Tool design | Iter 5 | 参数 schema 校验、缺参回注 | tool schema validation |",
        "| E. Loop / error handling | Iter 5 | 工具报错后重试 | ReAct observation / retry |",
        "| F. Memory / persistence | P2 demo | SQLite checkpoint 两轮记忆 | 单轮指标看不出收益 |",
        "| G. Context management | 未验证 | 压缩 / token 预算 | 长会话才需要 |",
        "| H. Observability | 部分 | 结果带 trace_id | 生产环境必需 |",
        "",
        "## 迭代总览",
        "",
        "| # | 方向 | 改动 | BFCL pass^k (mean) | RAG pass^k (mean) | 修复 | 回归 |",
        "|:---:|:---|:---|:---:|:---:|:---:|:---:|",
    ]
    for item in iterations:
        summary = item["summary"]
        compare = item["compare"]
        lines.append(
            f"| {item['index']} | {item['direction']} | {item['change']} | "
            f"{summary['bfcl_pass']}/{summary['bfcl_total']} ({summary['bfcl_mean']:.0%}) | "
            f"{summary['rag_pass']}/{summary['rag_total']} ({summary['rag_mean']:.0%}) | "
            f"{len(compare['fixed'])} | {len(compare['regressed'])} |"
        )

    for item in iterations:
        summary = item["summary"]
        lines += [
            "",
            f"## Iteration {item['index']}：{item['name']}",
            "",
            f"- 方向：{item['direction']}",
            f"- 公开参考：{item['knowledge_ref']}",
            f"- 改动：{item['change']}",
            f"- BFCL：pass^k {summary['bfcl_pass']}/{summary['bfcl_total']}，"
            f"mean {summary['bfcl_mean']:.0%}，分类 {summary['bfcl_by_kind']}",
            f"- BFCL 失败类型：{summary['bfcl_failures'] or '无'}",
            f"- RAG：pass^k {summary['rag_pass']}/{summary['rag_total']}，"
            f"mean {summary['rag_mean']:.0%}，分类 {summary['rag_by_type']}",
            f"- RAG 失败类型：{summary['rag_failures'] or '无'}",
            f"- 同类任务通过率：{item['same_class']}",
            f"- 修复：{item['compare']['fixed'] or '无'}",
            f"- 回归：{item['compare']['regressed'] or '无'}",
            f"- trace：{sum(1 for row in item['bfcl_results'] + item['rag_results'] if row.get('trace_id'))}"
            f"/{len(item['bfcl_results']) + len(item['rag_results'])} 条带 trace_id",
        ]

    lines += ["", "## 方向结论", "", "| 方向 | 轮次 | ΔBFCL | ΔRAG | 观察 |", "|:---|:---:|:---:|:---:|:---|"]
    for index, item in enumerate(iterations):
        if index == 0:
            continue
        previous = iterations[index - 1]["summary"]
        delta_bfcl = item["summary"]["bfcl_pass"] - previous["bfcl_pass"]
        delta_rag = item["summary"]["rag_pass"] - previous["rag_pass"]
        if delta_bfcl + delta_rag > 0:
            observation = "有帮助"
        elif delta_bfcl + delta_rag == 0:
            observation = "无变化"
        else:
            observation = "负向，需要回退或拆分"
        lines.append(
            f"| {item['direction']} | {item['index']} | {delta_bfcl:+d} | {delta_rag:+d} | {observation} |"
        )

    lines += [
        "",
        "## 结论与边界",
        "",
        "- 这是最小 Harness 优化循环，不是官方 benchmark 成绩：BFCL 工具是 stub，MultiHop 只评检索召回。",
        "- 每轮只改 prompt / tool 校验 / k / 检索器，没有改模型；修复/回归都按同一批 case 对比。",
        "- 样本量见运行参数；结论用于演示优化流程，不做统计显著性声明。",
        "- Memory / persistence、Context、Observability 属于架构方向，单轮 demo 无法体现指标收益，未纳入轮次。",
        "- 下一步：把同样的循环接到 τ² 适配器、BFCL 官方 scorer 和 outcome 断言上。",
    ]
    path = out_dir / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nreport: {path}")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--bfcl-simple", type=int, default=45)
    parser.add_argument("--bfcl-irrelevance", type=int, default=15)
    parser.add_argument("--multihop-per-type", type=int, default=15)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--configs", default="", help="逗号分隔，例如 baseline,routed_prompts")
    parser.add_argument("--families", default="bfcl,rag", help="bfcl / rag，逗号分隔")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", default=str(ROOT / "outputs" / "demo"))
    args = parser.parse_args(argv)

    bfcl_cases = load_bfcl_cases(args.bfcl_simple, args.bfcl_irrelevance, args.seed)
    rag_cases = load_multihop_cases(args.multihop_per_type, args.seed)
    corpus = load_multihop_corpus()
    print(f"BFCL cases={len(bfcl_cases)}  MultiHop cases={len(rag_cases)}  corpus={len(corpus)}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    iterations = []
    previous = None
    configs = CONFIGS
    if args.configs:
        selected = {name.strip() for name in args.configs.split(",") if name.strip()}
        configs = [config for config in CONFIGS if config["name"] in selected]

    for index, config in enumerate(configs[: args.iterations], 1):
        print(f"\n=== Iteration {index}: {config['name']} ===")
        families = {item.strip() for item in args.families.split(",") if item.strip()}
        bfcl_results = _run_bfcl(bfcl_cases, config, trials=args.trials) if "bfcl" in families else []
        rag_results = _run_rag(rag_cases, corpus, config, trials=args.trials) if "rag" in families else []
        current = bfcl_results + rag_results
        compare = _compare(previous, current)
        summary = _summary(bfcl_results, rag_results)
        item = {
            "index": index,
            "name": config["name"],
            "direction": config.get("direction", ""),
            "knowledge_ref": config.get("knowledge_ref", ""),
            "change": config.get("change", ""),
            "trials": args.trials,
            "config": config,
            "summary": summary,
            "same_class": _same_class(current),
            "compare": compare,
            "bfcl_results": bfcl_results,
            "rag_results": rag_results,
        }
        iterations.append(item)
        (out_dir / f"iteration_{index:02d}.json").write_text(
            json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        print(f"fixed={compare['fixed']} regressed={compare['regressed']}")
        previous = current

    _write_report(out_dir, iterations, args.trials)


if __name__ == "__main__":
    main()
