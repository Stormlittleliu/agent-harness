# -*- coding: utf-8 -*-
"""公开 benchmark 评测：RGB + MultiHop-RAG（使用 Agent 项目的 RAG 栈）。"""
import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.documents import Document  # noqa: E402

from evals.common import (  # noqa: E402
    DATASETS_DIR,
    REPORTS_DIR,
    build_rag_chain,
    build_store,
    format_context,
    load_jsonl,
    score_retrieval,
)

PUBLIC_DIR = DATASETS_DIR / "public"
MULTIHOP_CORPUS = PUBLIC_DIR / "multihop_corpus.json"
MAX_DOC_CHARS = 2000

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def run_rgb(limit=0):
    cases = load_jsonl(PUBLIC_DIR / "rag_rgb_sample.jsonl")
    if limit:
        cases = cases[:limit]
    chain = build_rag_chain()
    rows = []

    for index, case in enumerate(cases, 1):
        # RGB 采用 case-scoped 检索：每条样本只用自己的文档
        documents = [
            Document(
                page_content=item["text"][:MAX_DOC_CHARS],
                metadata={
                    "case_id": case["id"],
                    "doc_index": doc_index,
                    "label": item.get("label", ""),
                    "source": f"{case['id']}#{doc_index}",
                },
            )
            for doc_index, item in enumerate(case.get("documents", []))
        ]
        store = build_store(f"eval_rgb_{case['id']}_{int(time.time())}", documents)
        retrieved = store.similarity_search(case["question"], k=4)
        sources = [doc.metadata["source"] for doc in retrieved]
        context = format_context(retrieved)
        answer = chain.invoke({"input": case["question"], "context": context})

        category = case["category"]
        should_refuse = category == "rejection"
        if should_refuse:
            expected_points = ["资料中没有相关信息"]
        elif category == "integration":
            expected_points = case["gold_answers"]
        else:
            expected_points = [" 或 ".join(case["gold_answers"])]

        expected_sources = [doc.metadata["source"] for doc in documents if doc.metadata.get("label") == "positive"]
        hit, mrr = score_retrieval(sources, expected_sources)
        rows.append({
            "id": case["id"],
            "benchmark": "RGB",
            "category": f"rgb_{category}",
            "question": case["question"],
            "answer": answer,
            "expected_points": expected_points,
            "should_refuse": should_refuse,
            "retrieved_sources": sources,
            "retrieved_context": context,
            "expected_sources": expected_sources,
            "hit": hit,
            "mrr": mrr,
        })
        print(f"[RGB {index}/{len(cases)}] {case['id']} hit={hit}")
    return rows


def run_multihop(limit=0):
    cases = load_jsonl(PUBLIC_DIR / "rag_multihop_sample.jsonl")
    if limit:
        cases = cases[:limit]
    corpus = json.loads(MULTIHOP_CORPUS.read_text(encoding="utf-8"))
    documents = [
        Document(
            page_content=f"{item.get('title', '')}\n\n{item.get('body', '')}"[:MAX_DOC_CHARS],
            metadata={"title": item.get("title", ""), "url": item.get("url", ""), "source": item.get("title", "")},
        )
        for item in corpus
    ]
    print(f"[MultiHop] cases={len(cases)}, corpus={len(documents)}")
    store = build_store(f"eval_multihop_{int(time.time())}", documents)
    chain = build_rag_chain()
    rows = []

    for index, case in enumerate(cases, 1):
        retrieved = store.similarity_search(case["question"], k=4)
        sources = [doc.metadata["source"] for doc in retrieved]
        context = format_context(retrieved)
        answer = chain.invoke({"input": case["question"], "context": context})
        should_refuse = case["category"] == "null_query"
        expected_points = ["Insufficient information."] if should_refuse else case["gold_answers"]
        expected_sources = case.get("evidence_titles", [])
        hit, mrr = score_retrieval(sources, expected_sources)
        rows.append({
            "id": case["id"],
            "benchmark": "MultiHop-RAG",
            "category": f"multihop_{case['category']}",
            "question": case["question"],
            "answer": answer,
            "expected_points": expected_points,
            "should_refuse": should_refuse,
            "retrieved_sources": sources,
            "retrieved_context": context,
            "expected_sources": expected_sources,
            "hit": hit,
            "mrr": mrr,
        })
        print(f"[MultiHop {index}/{len(cases)}] {case['id']} hit={hit}")
    return rows


def summarize(rows):
    summary = {}
    for benchmark in sorted({row["benchmark"] for row in rows}):
        subset = [row for row in rows if row["benchmark"] == benchmark and row["hit"] is not None]
        hits = [row["hit"] for row in subset]
        mrrs = [row["mrr"] for row in subset]
        summary[benchmark] = {
            "scored": len(subset),
            "hit_at_4": round(sum(1 for item in hits if item) / len(hits), 4) if hits else 0.0,
            "mrr": round(sum(mrrs) / len(mrrs), 4) if mrrs else 0.0,
            "by_category": dict(Counter(row["category"] for row in rows if row["benchmark"] == benchmark)),
        }
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmarks", default="rgb,multihop")
    parser.add_argument("--rgb-limit", type=int, default=0)
    parser.add_argument("--multihop-limit", type=int, default=0)
    parser.add_argument("--skip-multihop", action="store_true")
    args = parser.parse_args()

    selected = [item.strip() for item in args.benchmarks.split(",") if item.strip()]
    rows = []
    if "rgb" in selected:
        rows.extend(run_rgb(args.rgb_limit))
    if "multihop" in selected and not args.skip_multihop:
        rows.extend(run_multihop(args.multihop_limit))

    summary = summarize(rows)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / "eval_public_results.json"
    md_path = REPORTS_DIR / "eval_public_retrieval.md"
    json_path.write_text(json.dumps({"summary": summary, "results": rows}, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 公开 Benchmark RAG 评测（检索层）",
        "",
        "| Benchmark | 参与检索评分 | Hit@4 | MRR | 分类分布 |",
        "|:---|:---:|:---:|:---:|:---|",
    ]
    for benchmark, item in summary.items():
        lines.append(f"| {benchmark} | {item['scored']} | {item['hit_at_4']:.2%} | {item['mrr']:.4f} | {item['by_category']} |")
    lines += ["", "## 明细", "", "| ID | Benchmark | 类别 | 问题 | 期望来源 | 检索 Top-4 | Hit |",
              "|:---|:---|:---|:---|:---|:---|:---:|"]
    for row in rows:
        expected = ", ".join(row["expected_sources"]) or "（应拒答/无证据）"
        sources = ", ".join(row["retrieved_sources"]) or "（空）"
        hit = "-" if row["hit"] is None else ("✅" if row["hit"] else "❌")
        lines.append(f"| {row['id']} | {row['benchmark']} | {row['category']} | {row['question']} | {expected} | {sources} | {hit} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n=== retrieval summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"results: {json_path}")
    print(f"report: {md_path}")
    print("\nnext: python evals/scripts/eval_judge.py --input "
          f"{json_path} --prefix eval_public")


if __name__ == "__main__":
    main()
