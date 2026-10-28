# -*- coding: utf-8 -*-
"""RAG 能力层评测：FrameworkAgent.invoke_tool → Scenario 工具 → 指标。

不经过模型决策：数据集里的 query 原样传给 `rag_retrieve` / `rag_summarize`，
一次调用拿回 content + artifact，再统计 Hit@K / MRR / 覆盖率 / 拒答 / 冲突。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quality.datasets import (  # noqa: E402
    DATASETS_DIR,
    build_retrievers,
    build_store,
    load_jsonl,
    split_documents,
)
from quality.metrics import (  # noqa: E402
    REFUSAL_MARKERS,
    detect_conflict,
    normalize,
    score_retrieval,
)
from quality.paths import RAG_OUT  # noqa: E402
from quality.rag_harness import (  # noqa: E402
    build_eval_agent,
    docs_from_artifact,
    result_parts,
    sources_from_artifact,
)


def run_retrieval(dataset=None, docs_dir=None, modes=("vector", "hybrid"), k=4, limit=0, out_dir=None):
    dataset = Path(dataset or DATASETS_DIR / "business" / "eval_set_all.jsonl")
    docs_dir = Path(docs_dir or DATASETS_DIR / "business" / "docs")
    out_dir = Path(out_dir or RAG_OUT)

    cases = load_jsonl(dataset)
    if limit:
        cases = cases[:limit]
    documents = split_documents(docs_dir)
    print(f"docs={len(documents)}, cases={len(cases)}")

    store = build_store(f"eval_retrieval_{int(time.time())}", documents)
    retrievers = build_retrievers(store, documents, k=k)
    agents = {mode: build_eval_agent(retrievers[mode]) for mode in modes}

    results = []
    for index, case in enumerate(cases, 1):
        expected = [str(item) for item in case.get("expected_sources", [])]
        row = {
            "id": case["id"],
            "category": case["category"],
            "question": case["question"],
            "expected_sources": expected,
        }
        for mode in modes:
            _, artifact = result_parts(
                agents[mode].invoke_tool("rag_retrieve", {"query": case["question"], "k": k})
            )
            sources = sources_from_artifact(artifact)
            hit, mrr = score_retrieval(sources, expected)
            row[mode] = {"sources": sources, "hit": hit, "mrr": mrr}
        results.append(row)
        print(f"[{index}/{len(cases)}] {case['id']} {case['category']}")

    scored = [row for row in results if row["expected_sources"]]
    summary = {
        "dataset": str(dataset),
        "total": len(results),
        "scored": len(scored),
        "by_category": dict(Counter(row["category"] for row in results)),
    }
    for mode in modes:
        hits = [row[mode]["hit"] for row in scored]
        mrrs = [row[mode]["mrr"] for row in scored]
        summary[mode] = {
            "hit_at_k": round(sum(1 for item in hits if item) / len(hits), 4) if hits else 0.0,
            "mrr": round(sum(mrrs) / len(mrrs), 4) if mrrs else 0.0,
            "hits": sum(1 for item in hits if item),
            "count": len(hits),
        }

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "eval_retrieval.json"
    md_path = out_dir / "eval_retrieval.md"
    json_path.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# RAG 检索层评测",
        "",
        f"- 样本：{summary['total']}（参与检索评分 {summary['scored']}）",
        f"- 分类分布：{summary['by_category']}",
        "",
        "| 模式 | Hit@K | MRR | 命中/总数 |",
        "|:---|:---:|:---:|:---:|",
    ]
    for mode in modes:
        item = summary[mode]
        lines.append(f"| {mode} | {item['hit_at_k']:.2%} | {item['mrr']:.4f} | {item['hits']}/{item['count']} |")
    lines += ["", "## 明细", "", "| ID | 类别 | 问题 | 期望来源 | " + " | ".join(f"{mode} Top-K" for mode in modes) + " |",
              "|:---|:---|:---|:---|" + "|".join(":---" for _ in modes) + "|"]
    for row in results:
        expected = ", ".join(row["expected_sources"]) or "（应拒答）"
        cells = []
        for mode in modes:
            sources = ", ".join(row[mode]["sources"]) or "（空）"
            if row[mode]["hit"] is None:
                cells.append(sources)
            else:
                cells.append(("✅ " if row[mode]["hit"] else "❌ ") + sources)
        lines.append(f"| {row['id']} | {row['category']} | {row['question']} | {expected} | " + " | ".join(cells) + " |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n=== summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {md_path}")
    print(f"details: {json_path}")
    return summary


def run_generation(dataset=None, docs_dir=None, mode="hybrid", k=4, limit=0, out_dir=None):
    dataset = Path(dataset or DATASETS_DIR / "business" / "eval_set_all.jsonl")
    docs_dir = Path(docs_dir or DATASETS_DIR / "business" / "docs")
    out_dir = Path(out_dir or RAG_OUT)

    cases = load_jsonl(dataset)
    if limit:
        cases = cases[:limit]
    documents = split_documents(docs_dir)
    print(f"docs={len(documents)}, cases={len(cases)}, mode={mode}")

    store = build_store(f"eval_generation_{int(time.time())}", documents)
    retriever = build_retrievers(store, documents, k=k)[mode]
    agent = build_eval_agent(retriever)

    results = []
    for index, case in enumerate(cases, 1):
        answer, artifact = result_parts(
            agent.invoke_tool("rag_summarize", {"query": case["question"]})
        )
        docs = docs_from_artifact(artifact)
        sources = sources_from_artifact(artifact)
        context = "\n\n".join(doc.page_content for doc in docs)
        conflict_flag, conflict_reasons = detect_conflict(docs, case["question"])

        normalized = normalize(answer)
        expected_points = case.get("expected_points", [])
        matched = [point for point in expected_points if normalize(point) in normalized]
        coverage = len(matched) / len(expected_points) if expected_points else 1.0
        should_refuse = bool(case.get("should_refuse"))
        refused = any(marker in answer for marker in REFUSAL_MARKERS)
        passed = refused if should_refuse else coverage >= 0.5

        results.append({
            "id": case["id"],
            "category": case["category"],
            "question": case["question"],
            "answer": answer,
            "expected_points": expected_points,
            "matched_points": matched,
            "coverage": round(coverage, 4),
            "refused": refused,
            "should_refuse": should_refuse,
            "passed": passed,
            "retrieved_sources": sources,
            "retrieved_context": context,
            "conflict_flag": conflict_flag,
            "conflict_reasons": conflict_reasons,
        })
        flag = " [CONFLICT]" if conflict_flag else ""
        print(f"[{index}/{len(cases)}] {case['id']} {case['category']} coverage={coverage:.2f} refused={refused}{flag}")

    scored = [row for row in results if not row["should_refuse"]]
    refusals = [row for row in results if row["should_refuse"]]
    summary = {
        "dataset": str(dataset),
        "mode": mode,
        "total": len(results),
        "by_category": dict(Counter(row["category"] for row in results)),
        "answer_avg_coverage": round(sum(row["coverage"] for row in scored) / len(scored), 4) if scored else 0.0,
        "answer_full_coverage": sum(1 for row in scored if row["coverage"] == 1.0),
        "answer_count": len(scored),
        "refusal_correct": sum(1 for row in refusals if row["refused"]),
        "refusal_count": len(refusals),
        "passed": sum(1 for row in results if row["passed"]),
        "conflict_flagged": sum(1 for row in results if row["conflict_flag"]),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "eval_generation.json"
    md_path = out_dir / "eval_generation.md"
    json_path.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# RAG 生成层评测",
        "",
        f"- 检索模式：{mode}",
        f"- 样本总数：{summary['total']}",
        f"- 答案题平均覆盖：{summary['answer_avg_coverage']:.2%}",
        f"- 答案题完整覆盖：{summary['answer_full_coverage']}/{summary['answer_count']}",
        f"- 拒答正确：{summary['refusal_correct']}/{summary['refusal_count']}",
        f"- 自动判定通过：{summary['passed']}/{summary['total']}",
        f"- 冲突标记：{summary['conflict_flagged']} 条",
        "",
        "## 明细",
        "",
        "| ID | 类别 | 问题 | 覆盖 | 拒答 | 回答摘要 |",
        "|:---|:---|:---|:---:|:---:|:---|",
    ]
    for row in results:
        answer = row["answer"].replace("\n", " ").replace("|", "\\|")
        if len(answer) > 100:
            answer = answer[:100] + "..."
        lines.append(f"| {row['id']} | {row['category']} | {row['question']} | {row['coverage']:.0%} | {'是' if row['refused'] else '否'} | {answer} |")

    lines += ["", "## 来源与冲突标记（独立输出）", "", "| ID | 检索来源 | 冲突 | 原因 |", "|:---|:---|:---:|:---|"]
    for row in results:
        sources = ", ".join(row["retrieved_sources"]) or "（空）"
        reasons = "; ".join(row["conflict_reasons"]) or "-"
        lines.append(f"| {row['id']} | {sources} | {'是' if row['conflict_flag'] else '否'} | {reasons} |")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n=== summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {md_path}")
    print(f"details: {json_path}")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="RAG 能力层评测")
    parser.add_argument("task", choices=["retrieval", "generation"])
    parser.add_argument("--dataset")
    parser.add_argument("--docs-dir")
    parser.add_argument("--mode", default="hybrid", choices=["vector", "hybrid"])
    parser.add_argument("--modes", default="vector,hybrid")
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out-dir")
    args = parser.parse_args(argv)

    if args.task == "retrieval":
        modes = tuple(item.strip() for item in args.modes.split(",") if item.strip())
        run_retrieval(args.dataset, args.docs_dir, modes, args.k, args.limit, args.out_dir)
    else:
        run_generation(args.dataset, args.docs_dir, args.mode, args.k, args.limit, args.out_dir)


if __name__ == "__main__":
    main()
