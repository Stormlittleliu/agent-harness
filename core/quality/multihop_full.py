# -*- coding: utf-8 -*-
"""MultiHop-RAG 全量检索评测（官方数据 + 官方指标定义）。

- 语料：官方 data/corpus.json，609 篇，全量；
- 问题：官方 data/MultiHopRAG.json，2556 条，全量；
- 指标：直接复用官方 retrieval_evaluate.py 的 calculate_metrics
  （Hits@4、Hits@10、MAP@10、MRR@10），null_query 按官方口径跳过；
- 检索器：本地 BGE + Chroma，k=10（官方脚本需要 top-10 才能算 Hits@10）。
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.documents import Document  # noqa: E402

from core.quality.datasets import build_store  # noqa: E402
from core.quality.paths import PUBLIC_OUT  # noqa: E402

MULTIHOP_REPO = Path(r"E:\CODE\benchmarks\MultiHop-RAG")
CORPUS_PATH = MULTIHOP_REPO / "data" / "corpus.json"
QUERIES_PATH = MULTIHOP_REPO / "data" / "MultiHopRAG.json"

sys.path.insert(0, str(MULTIHOP_REPO))
from retrieval_evaluate import calculate_metrics  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="MultiHop-RAG 全量检索评测")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 条；0 表示全量")
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--out-dir", default=str(PUBLIC_OUT))
    args = parser.parse_args(argv)

    corpus = load_json(CORPUS_PATH)
    queries = load_json(QUERIES_PATH)
    if args.limit:
        queries = queries[: args.limit]

    documents = [
        Document(
            page_content=f"{item.get('title', '')}\n\n{item.get('body', '')}",
            metadata={
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "url": item.get("url", ""),
            },
        )
        for item in corpus
    ]
    store = build_store(f"official_multihop_{int(datetime.now().timestamp())}", documents)
    retriever = store.as_retriever(search_kwargs={"k": args.k})

    records = []
    for index, query in enumerate(queries, 1):
        docs = retriever.invoke(query["query"])
        retrieved = [f"{doc.metadata.get('title', '')}\n{doc.page_content}" for doc in docs]
        gold = [item.get("fact", "") for item in query.get("evidence_list", [])]
        is_null = query.get("question_type") == "null_query"

        records.append({
            "query": query["query"],
            "answer": query.get("answer", ""),
            "question_type": query.get("question_type", ""),
            "is_null": is_null,
            "retrieval_list": [{"text": text} for text in retrieved],
            "gold_list": [{"fact": fact} for fact in gold],
            "retrieved_titles": [doc.metadata.get("title", "") for doc in docs],
            "gold_titles": [item.get("title", "") for item in query.get("evidence_list", [])],
            "gold_facts": gold,
        })
        if index % 100 == 0:
            print(f"[{index}/{len(queries)}]")

    valid = [row for row in records if not row["is_null"]]
    metrics = calculate_metrics(
        [[item["text"] for item in row["retrieval_list"]] for row in valid],
        [[item["fact"] for item in row["gold_list"]] for row in valid],
    )

    by_type = {}
    for question_type in sorted({row["question_type"] for row in valid}):
        subset = [row for row in valid if row["question_type"] == question_type]
        by_type[question_type] = calculate_metrics(
            [[item["text"] for item in row["retrieval_list"]] for row in subset],
            [[item["fact"] for item in row["gold_list"]] for row in subset],
        )

    summary = {
        "dataset": str(QUERIES_PATH),
        "corpus": str(CORPUS_PATH),
        "corpus_size": len(corpus),
        "queries_total": len(records),
        "queries_scored": len(valid),
        "null_queries_skipped": len(records) - len(valid),
        "k": args.k,
        "embedding": "bge-small-zh-v1.5 (local)",
        "metrics": metrics,
        "by_question_type": by_type,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "multihop_full.json"
    md_path = out_dir / "multihop_full.md"
    # 官方指标已在内存中算完；落盘时去掉完整检索文本，避免 270MB 大文件。
    compact = [
        {key: value for key, value in row.items() if key not in {"retrieval_list", "gold_list"}}
        for row in records
    ]
    json_path.write_text(
        json.dumps({"summary": summary, "results": compact}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# MultiHop-RAG 全量检索评测",
        "",
        f"- 语料：{summary['corpus_size']} 篇",
        f"- 问题：{summary['queries_total']} 条，参与评分 {summary['queries_scored']} 条",
        f"- null_query 跳过：{summary['null_queries_skipped']} 条",
        f"- 检索：本地 BGE + Chroma，k={args.k}",
        "",
        "| 指标 | 数值 |",
        "|:---|:---:|",
    ]
    for name, value in metrics.items():
        lines.append(f"| {name} | {value:.4f} |")
    lines += ["", "## 分类", "", "| 类型 | 数量 | Hits@4 | MRR@10 |", "|:---|:---:|:---:|:---:|"]
    for question_type, item in by_type.items():
        count = sum(1 for row in valid if row["question_type"] == question_type)
        lines.append(f"| {question_type} | {count} | {item['Hits@4']:.4f} | {item['MRR@10']:.4f} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n=== summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nreport: {md_path}")
    print(f"details: {json_path}")


if __name__ == "__main__":
    main()
