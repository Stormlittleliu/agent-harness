# -*- coding: utf-8 -*-
"""RAG 检索层独立评测：纯向量 vs 混合检索。

只测检索，不调用聊天模型：
- Hit@K：期望来源是否出现在前 K 条
- MRR：第一个正确来源排名的倒数
- 对 unanswerable 样本不计算检索命中，只记录 Top-K 来源供人工检查

用法：
    conda run -n langchain python scripts/eval_rag.py
    conda run -n langchain python scripts/eval_rag.py --limit 3
    conda run -n langchain python scripts/eval_rag.py --eval-set <path>
"""
import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from kbrag.retrievers import get_hybrid_retriever, get_vector_retriever  # noqa: E402

DEFAULT_EVAL_SET = Path(r"E:\CODE\ag_learn\evals\rag\eval_set.jsonl")
DEFAULT_OUT_DIR = ROOT / "reports"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def load_cases(path: Path):
    cases = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def source_name(doc) -> str:
    source = str((doc.metadata or {}).get("source", ""))
    return os.path.basename(source).lower()


def matches(actual: str, expected: str) -> bool:
    actual = actual.lower()
    expected = expected.lower()
    return actual == expected or actual.endswith(expected) or expected.endswith(actual)


def evaluate(cases, modes):
    retrievers = {
        "vector": get_vector_retriever(),
        "hybrid": get_hybrid_retriever(),
    }
    results = []

    for index, case in enumerate(cases, 1):
        question = case["question"]
        expected = [str(item).lower() for item in case.get("expected_sources", [])]
        row = {
            "id": case["id"],
            "category": case["category"],
            "question": question,
            "expected_sources": expected,
            "should_refuse": bool(case.get("should_refuse")),
        }

        for mode in modes:
            docs = retrievers[mode].invoke(question)
            sources = [source_name(doc) for doc in docs]

            if expected:
                hit = any(matches(source, exp) for source in sources for exp in expected)
                mrr = 0.0
                for rank, source in enumerate(sources, 1):
                    if any(matches(source, exp) for exp in expected):
                        mrr = 1.0 / rank
                        break
            else:
                hit = None
                mrr = None

            row[mode] = {"sources": sources, "hit": hit, "mrr": mrr}

        results.append(row)
        print(f"[{index}/{len(cases)}] {case['id']} {case['category']}")

    return results


def summarize(results, modes):
    scored = [row for row in results if row.get("expected_sources")]
    summary = {"total": len(results), "scored": len(scored), "by_category": dict(Counter(row["category"] for row in results))}

    for mode in modes:
        hits = [row[mode]["hit"] for row in scored]
        mrrs = [row[mode]["mrr"] for row in scored]
        summary[mode] = {
            "hit_at_k": round(sum(1 for item in hits if item) / len(hits), 4) if hits else 0.0,
            "mrr": round(sum(mrrs) / len(mrrs), 4) if mrrs else 0.0,
            "hits": sum(1 for item in hits if item),
            "count": len(hits),
        }
    return summary


def write_report(results, summary, modes, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "eval_retrieval.json"
    md_path = out_dir / "eval_retrieval.md"

    json_path.write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# RAG 检索层评测报告",
        "",
        f"- 样本总数：{summary['total']}",
        f"- 参与检索评分：{summary['scored']}（排除 unanswerable）",
        f"- 分类分布：{summary['by_category']}",
        "",
        "## 汇总",
        "",
        "| 检索模式 | Hit@K | MRR | 命中/总数 |",
        "|:---|:---:|:---:|:---:|",
    ]
    for mode in modes:
        item = summary[mode]
        lines.append(f"| {mode} | {item['hit_at_k']:.2%} | {item['mrr']:.4f} | {item['hits']}/{item['count']} |")

    lines += [
        "",
        "## 明细",
        "",
        "| ID | 类别 | 问题 | 期望来源 | " + " | ".join(f"{mode} Top-K" for mode in modes) + " |",
        "|:---|:---|:---|:---|" + "|".join(":---" for _ in modes) + "|",
    ]
    for row in results:
        expected = ", ".join(row["expected_sources"]) or "（应拒答）"
        question = row["question"].replace("|", "\\|")
        cells = []
        for mode in modes:
            sources = ", ".join(row[mode]["sources"]) or "（空）"
            if row[mode]["hit"] is None:
                cells.append(sources)
            else:
                mark = "✅" if row[mode]["hit"] else "❌"
                cells.append(f"{mark} {sources}")
        lines.append(f"| {row['id']} | {row['category']} | {question} | {expected} | " + " | ".join(cells) + " |")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-set", default=str(DEFAULT_EVAL_SET))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--modes", default="vector,hybrid")
    args = parser.parse_args()

    cases = load_cases(Path(args.eval_set))
    if args.limit:
        cases = cases[: args.limit]
    modes = [mode.strip() for mode in args.modes.split(",") if mode.strip()]

    results = evaluate(cases, modes)
    summary = summarize(results, modes)
    json_path, md_path = write_report(results, summary, modes, Path(args.out_dir))

    print("\n=== summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nreport: {md_path}")
    print(f"details: {json_path}")


if __name__ == "__main__":
    main()
