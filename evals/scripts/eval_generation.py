# -*- coding: utf-8 -*-
"""RAG 生成层评测：使用 Agent 项目的 RAG 提示词与模型。

输出 reports/eval_generation.json，供 eval_judge.py 复核。
"""
import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.common import (  # noqa: E402
    DATASETS_DIR,
    REPORTS_DIR,
    build_rag_chain,
    build_retrievers,
    build_store,
    format_context,
    load_jsonl,
    source_name,
    split_documents,
)

REFUSAL_MARKERS = [
    "没有", "无法", "未提供", "不清楚", "不能确定", "不知道",
    "无相关", "暂无", "不包含", "未包含", "资料不足", "未提及",
]

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", str(text)).lower()


def detect_conflict(docs, question: str):
    texts = " ".join(doc.page_content for doc in docs)
    sources = {source_name(doc) for doc in docs}
    reasons = []
    q = question.lower()
    size_question = bool(re.search(r"尺码|码|身高|体重|size|斤|kg|公斤|号", q, re.IGNORECASE))
    new_product = bool(re.search(r"新品|防风外套|春季新品", q))
    has_jin = "斤" in texts
    has_kg = bool(re.search(r"kg|千克|公斤", texts, re.IGNORECASE))
    size_context = bool(re.search(r"尺码|建议尺码|size", texts, re.IGNORECASE))
    if size_question and has_jin and has_kg and size_context:
        reasons.append("unit_mismatch: 斤 vs kg")
    if new_product and {"尺码推荐.txt", "新品推荐.md"} <= sources and has_jin and has_kg:
        reasons.append("size_conflict: 尺码表与新品推荐同时命中")
    return bool(reasons), reasons


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(DATASETS_DIR / "business" / "eval_set_all.jsonl"))
    parser.add_argument("--docs-dir", default=str(DATASETS_DIR / "business" / "docs"))
    parser.add_argument("--out-dir", default=str(REPORTS_DIR))
    parser.add_argument("--mode", default="hybrid", choices=["vector", "hybrid"])
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    cases = load_jsonl(Path(args.dataset))
    if args.limit:
        cases = cases[:args.limit]

    documents = split_documents(Path(args.docs_dir))
    print(f"docs={len(documents)}, cases={len(cases)}, mode={args.mode}")
    store = build_store(f"eval_generation_{int(time.time())}", documents)
    retriever = build_retrievers(store, documents, k=args.k)[args.mode]
    chain = build_rag_chain()

    results = []
    for index, case in enumerate(cases, 1):
        docs = retriever.invoke(case["question"])
        context = format_context(docs)
        answer = chain.invoke({"input": case["question"], "context": context})
        sources = [source_name(doc) for doc in docs]
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
        "dataset": str(args.dataset),
        "mode": args.mode,
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

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "eval_generation.json"
    md_path = out_dir / "eval_generation.md"
    json_path.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# RAG 生成层评测",
        "",
        f"- 检索模式：{args.mode}",
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


if __name__ == "__main__":
    main()
