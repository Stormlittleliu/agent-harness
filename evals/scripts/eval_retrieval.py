# -*- coding: utf-8 -*-
"""RAG 检索层评测：纯向量 vs 混合检索（使用 Agent 项目的 RAG 栈）。"""
import argparse
import json
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
    build_retrievers,
    build_store,
    load_jsonl,
    score_retrieval,
    source_name,
    split_documents,
)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default=str(DATASETS_DIR / "business" / "eval_set_all.jsonl"))
    parser.add_argument("--docs-dir", default=str(DATASETS_DIR / "business" / "docs"))
    parser.add_argument("--out-dir", default=str(REPORTS_DIR))
    parser.add_argument("--modes", default="vector,hybrid")
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    cases = load_jsonl(Path(args.dataset))
    if args.limit:
        cases = cases[:args.limit]

    documents = split_documents(Path(args.docs_dir))
    print(f"docs={len(documents)}, cases={len(cases)}")
    store = build_store(f"eval_retrieval_{int(time.time())}", documents)
    retrievers = build_retrievers(store, documents, k=args.k)
    modes = [item.strip() for item in args.modes.split(",") if item.strip()]

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
            docs = retrievers[mode].invoke(case["question"])
            sources = [source_name(doc) for doc in docs]
            hit, mrr = score_retrieval(sources, expected)
            row[mode] = {"sources": sources, "hit": hit, "mrr": mrr}
        results.append(row)
        print(f"[{index}/{len(cases)}] {case['id']} {case['category']}")

    scored = [row for row in results if row["expected_sources"]]
    summary = {
        "dataset": str(args.dataset),
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

    out_dir = Path(args.out_dir)
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


if __name__ == "__main__":
    main()
