# -*- coding: utf-8 -*-
"""在公开 benchmark（RGB / MultiHop-RAG）上跑 RAG 流水线。

流程：
1. 为每个 benchmark 建独立的内存 Chroma 集合（不污染业务知识库）；
2. 对每条样本检索 Top-K，用项目现有严格拒答 Prompt 生成回答；
3. 计算检索 Hit@K / MRR，输出结果供 eval_rag_judge.py 复核。

用法：
    conda run -n langchain python scripts/eval_public_benchmarks.py --rgb-limit 2 --skip-multihop
    conda run -n langchain python scripts/eval_public_benchmarks.py
"""
import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from langchain_chroma import Chroma  # noqa: E402
from langchain_community.chat_models.tongyi import ChatTongyi  # noqa: E402
from langchain_core.documents import Document  # noqa: E402
from langchain_core.output_parsers import StrOutputParser  # noqa: E402
from langchain_core.prompts import ChatPromptTemplate  # noqa: E402

from kbrag import config  # noqa: E402
from kbrag.prompts import CHAT_SYSTEM_TEMPLATE, format_docs  # noqa: E402
from kbrag.providers import get_embedding  # noqa: E402

EVAL_DIR = Path(r"E:\CODE\ag_learn\evals\public")
MULTIHOP_CORPUS = Path(r"E:\CODE\benchmarks\MultiHop-RAG\data\corpus.json")
OUT_DIR = ROOT / "reports"
BATCH_SIZE = 10
MAX_DOC_CHARS = 2000

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def load_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", str(text)).lower()


def build_store(collection_name: str, docs):
    store = Chroma(collection_name=collection_name, embedding_function=get_embedding())
    total = len(docs)
    for start in range(0, total, BATCH_SIZE):
        batch = docs[start:start + BATCH_SIZE]
        for attempt in range(3):
            try:
                store.add_documents(batch)
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == 2:
                    raise
                print(f"  embedding batch {start} failed ({exc}), retry {attempt + 1}")
                time.sleep(2)
        if start and start % 100 == 0:
            print(f"  indexed {start}/{total}")
    print(f"  indexed {total} docs into {collection_name}")
    return store


def build_chain():
    model = ChatTongyi(model=config.chat_model_name, temperature=0)
    prompt = ChatPromptTemplate.from_messages([
        ("system", CHAT_SYSTEM_TEMPLATE),
        ("user", "请回答用户提问：{input}"),
    ])
    return prompt | model | StrOutputParser()


def score_retrieval(retrieved_sources, expected_sources):
    if not expected_sources:
        return None, None
    normalized_expected = [normalize(item) for item in expected_sources]
    hit = any(
        any(normalize(source) == exp or normalize(source).endswith(exp) or exp.endswith(normalize(source))
            for exp in normalized_expected)
        for source in retrieved_sources
    )
    mrr = 0.0
    for rank, source in enumerate(retrieved_sources, 1):
        if any(normalize(source) == exp or normalize(source).endswith(exp) or exp.endswith(normalize(source))
               for exp in normalized_expected):
            mrr = 1.0 / rank
            break
    return hit, mrr


def run_rgb(limit=0):
    cases = load_jsonl(EVAL_DIR / "rag_rgb_sample.jsonl")
    if limit:
        cases = cases[:limit]

    chain = build_chain()
    rows = []

    for index, case in enumerate(cases, 1):
        # RGB 的评测协议是 case-scoped：每条样本只用自己的文档，
        # 否则 rejection 题会检索到其它 case 的正例，导致“该拒答却答对”的假象。
        docs = [
            Document(
                page_content=item["text"][:MAX_DOC_CHARS],
                metadata={
                    "benchmark": "RGB",
                    "case_id": case["id"],
                    "doc_index": doc_index,
                    "label": item.get("label", ""),
                    "source": f"{case['id']}#{doc_index}",
                },
            )
            for doc_index, item in enumerate(case.get("documents", []))
        ]

        store = build_store(f"eval_rgb_{case['id']}_{int(time.time())}", docs)
        retrieved = store.similarity_search(case["question"], k=4)
        sources = [doc.metadata["source"] for doc in retrieved]
        context = format_docs(retrieved)
        answer = chain.invoke({"context": context, "input": case["question"]})

        category = case["category"]
        should_refuse = category == "rejection"
        if should_refuse:
            expected_points = ["资料中没有相关信息"]
        elif category == "integration":
            expected_points = case["gold_answers"]
        else:
            expected_points = [" 或 ".join(case["gold_answers"])]

        expected_sources = [
            doc.metadata["source"] for doc in docs
            if doc.metadata.get("label") == "positive"
        ]
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
    cases = load_jsonl(EVAL_DIR / "rag_multihop_sample.jsonl")
    if limit:
        cases = cases[:limit]

    corpus = json.loads(MULTIHOP_CORPUS.read_text(encoding="utf-8"))
    docs = [
        Document(
            page_content=f"{item.get('title', '')}\n\n{item.get('body', '')}"[:MAX_DOC_CHARS],
            metadata={
                "benchmark": "MultiHop-RAG",
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "source": item.get("title", ""),
            },
        )
        for item in corpus
    ]

    print(f"[MultiHop] cases={len(cases)}, corpus={len(docs)}")
    store = build_store(f"eval_multihop_{int(time.time())}", docs)
    chain = build_chain()
    rows = []

    for index, case in enumerate(cases, 1):
        retrieved = store.similarity_search(case["question"], k=4)
        sources = [doc.metadata["source"] for doc in retrieved]
        context = format_docs(retrieved)
        answer = chain.invoke({"context": context, "input": case["question"]})

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


def summarize_retrieval(rows):
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


def write_reports(rows, summary):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / "eval_public_results.json"
    md_path = OUT_DIR / "eval_public_retrieval.md"

    json_path.write_text(
        json.dumps({"retrieval_summary": summary, "results": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# 公开 Benchmark RAG 评测（检索层）",
        "",
        "| Benchmark | 参与检索评分 | Hit@4 | MRR | 分类分布 |",
        "|:---|:---:|:---:|:---:|:---|",
    ]
    for benchmark, item in summary.items():
        lines.append(
            f"| {benchmark} | {item['scored']} | {item['hit_at_4']:.2%} | "
            f"{item['mrr']:.4f} | {item['by_category']} |"
        )

    lines += [
        "",
        "## 明细",
        "",
        "| ID | Benchmark | 类别 | 问题 | 期望来源 | 检索 Top-4 | Hit |",
        "|:---|:---|:---|:---|:---|:---|:---:|",
    ]
    for row in rows:
        expected = ", ".join(row["expected_sources"]) or "（应拒答/无证据）"
        sources = ", ".join(row["retrieved_sources"]) or "（空）"
        hit = "-" if row["hit"] is None else ("✅" if row["hit"] else "❌")
        lines.append(
            f"| {row['id']} | {row['benchmark']} | {row['category']} | {row['question']} | "
            f"{expected} | {sources} | {hit} |"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


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

    summary = summarize_retrieval(rows)
    json_path, md_path = write_reports(rows, summary)

    print("\n=== retrieval summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nresults: {json_path}")
    print(f"report: {md_path}")
    print("\nnext: conda run -n langchain python scripts/eval_rag_judge.py "
          f"--input {json_path} --prefix eval_public")


if __name__ == "__main__":
    main()
