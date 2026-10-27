# -*- coding: utf-8 -*-
"""RAG 生成层评测：严格拒答版 Prompt + 来源/冲突独立标记。

设计：
- 检索结果只以纯文本进入上下文，不把来源名、引用标记塞进 context；
- 生成后单独打印 retrieved_sources、cited_sources、conflict_flag；
- conflict_flag 只做运行中标记，不改变回答行为（冲突文档后续再处理）。
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from langchain_community.chat_models.tongyi import ChatTongyi  # noqa: E402
from langchain_core.output_parsers import StrOutputParser  # noqa: E402
from langchain_core.prompts import ChatPromptTemplate  # noqa: E402

from kbrag import config  # noqa: E402
from kbrag.prompts import CHAT_SYSTEM_TEMPLATE, format_docs  # noqa: E402
from kbrag.retrievers import get_retriever  # noqa: E402

DEFAULT_EVAL_SET = Path(r"E:\CODE\ag_learn\evals\rag\eval_set_all.jsonl")
DEFAULT_OUT_DIR = ROOT / "reports"

REFUSAL_MARKERS = [
    "没有", "无法", "未提供", "不清楚", "不能确定",
    "无相关", "暂无", "不包含", "未包含", "资料不足", "未提及",
]

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
    return os.path.basename(str((doc.metadata or {}).get("source", "")))


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", str(text)).lower()


def build_chain():
    model = ChatTongyi(model=config.chat_model_name, temperature=0)
    prompt = ChatPromptTemplate.from_messages([
        ("system", CHAT_SYSTEM_TEMPLATE),
        ("user", "请回答用户提问：{input}"),
    ])
    return prompt | model | StrOutputParser()


def detect_conflict(docs, question: str):
    """运行中标记潜在冲突；不改变回答行为。

    只在“问题确实在问尺码/身高体重”且检索结果同时包含斤与 kg 时标记，
    避免把所有带尺码文档的问题都误标。
    """
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


CITATION_PATTERN = re.compile(r"\[来源[:：]\s*([^\]]+)\]")


def check_citations(answer: str, sources):
    """独立检查回答里的引用标记；不往上下文里塞来源信息。"""
    cited = [item.strip() for item in CITATION_PATTERN.findall(answer)]
    if not cited:
        return {"cited": [], "valid": None, "note": "no inline citations"}

    valid_flags = []
    for item in cited:
        normalized = normalize(item)
        valid_flags.append(any(normalized in normalize(source) or normalize(source) in normalized for source in sources))
    return {"cited": cited, "valid": all(valid_flags), "note": ""}


def score_answer(answer: str, expected_points):
    normalized = normalize(answer)
    hits = [point for point in expected_points if normalize(point) in normalized]
    coverage = len(hits) / len(expected_points) if expected_points else 1.0
    refused = any(marker in answer for marker in REFUSAL_MARKERS)
    return coverage, hits, refused


def evaluate(cases, mode):
    retriever = get_retriever(mode)
    chain = build_chain()
    results = []

    for index, case in enumerate(cases, 1):
        docs = retriever.invoke(case["question"])
        context = format_docs(docs)
        answer = chain.invoke({"context": context, "input": case["question"]})

        sources = [source_name(doc) for doc in docs]
        conflict_flag, conflict_reasons = detect_conflict(docs, case["question"])
        citation = check_citations(answer, sources)
        coverage, hits, refused = score_answer(answer, case.get("expected_points", []))
        should_refuse = bool(case.get("should_refuse"))
        passed = refused if should_refuse else coverage >= 0.5

        results.append({
            "id": case["id"],
            "category": case["category"],
            "question": case["question"],
            "answer": answer,
            "expected_points": case.get("expected_points", []),
            "matched_points": hits,
            "coverage": round(coverage, 4),
            "refused": refused,
            "should_refuse": should_refuse,
            "passed": passed,
            "retrieved_sources": sources,
            "retrieved_context": context,
            "citation": citation,
            "conflict_flag": conflict_flag,
            "conflict_reasons": conflict_reasons,
        })

        flag = " [CONFLICT]" if conflict_flag else ""
        print(f"[{index}/{len(cases)}] {case['id']} {case['category']} coverage={coverage:.2f} refused={refused}{flag}")
        print(f"    sources: {', '.join(sources) or '(empty)'}")
        if citation["cited"]:
            print(f"    citations: {citation['cited']} valid={citation['valid']}")

    return results


def recompute_flags(results, mode):
    """不重新生成回答，只重算来源、冲突标记和引用检查。"""
    retriever = get_retriever(mode)
    for row in results:
        docs = retriever.invoke(row["question"])
        row["retrieved_sources"] = [source_name(doc) for doc in docs]
        row["retrieved_context"] = format_docs(docs)
        row["conflict_flag"], row["conflict_reasons"] = detect_conflict(docs, row["question"])
        row["citation"] = check_citations(row["answer"], row["retrieved_sources"])
    return results


def summarize(results):
    total = len(results)
    scored = [row for row in results if not row["should_refuse"]]
    refusals = [row for row in results if row["should_refuse"]]

    return {
        "total": total,
        "by_category": dict(Counter(row["category"] for row in results)),
        "answer_avg_coverage": round(sum(row["coverage"] for row in scored) / len(scored), 4) if scored else 0.0,
        "answer_full_coverage": sum(1 for row in scored if row["coverage"] == 1.0),
        "answer_count": len(scored),
        "refusal_correct": sum(1 for row in refusals if row["refused"]),
        "refusal_count": len(refusals),
        "passed": sum(1 for row in results if row["passed"]),
        "conflict_flagged": sum(1 for row in results if row["conflict_flag"]),
        "citation_inline": sum(1 for row in results if row["citation"]["cited"]),
        "citation_valid": sum(1 for row in results if row["citation"]["valid"] is True),
    }


def write_report(results, summary, mode, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "eval_generation.json"
    md_path = out_dir / "eval_generation.md"

    json_path.write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# RAG 生成层评测报告",
        "",
        f"- 检索模式：{mode}",
        f"- 样本总数：{summary['total']}",
        f"- 答案题平均要点覆盖：{summary['answer_avg_coverage']:.2%}",
        f"- 答案题完整覆盖：{summary['answer_full_coverage']}/{summary['answer_count']}",
        f"- 拒答正确：{summary['refusal_correct']}/{summary['refusal_count']}",
        f"- 自动判定通过：{summary['passed']}/{summary['total']}",
        f"- 冲突标记：{summary['conflict_flagged']} 条",
        f"- 回答内联引用：{summary['citation_inline']} 条，其中有效 {summary['citation_valid']} 条",
        "",
        "## 明细",
        "",
        "| ID | 类别 | 问题 | 覆盖率 | 拒答 | 回答摘要 |",
        "|:---|:---|:---|:---:|:---:|:---|",
    ]
    for row in results:
        answer = row["answer"].replace("\n", " ").replace("|", "\\|")
        if len(answer) > 100:
            answer = answer[:100] + "..."
        lines.append(
            f"| {row['id']} | {row['category']} | {row['question']} | "
            f"{row['coverage']:.0%} | {'是' if row['refused'] else '否'} | {answer} |"
        )

    lines += [
        "",
        "## 来源与冲突标记（独立输出，不进入上下文）",
        "",
        "| ID | 检索来源 | 冲突标记 | 冲突原因 | 回答内引用 | 引用有效 |",
        "|:---|:---|:---:|:---|:---|:---:|",
    ]
    for row in results:
        sources = ", ".join(row["retrieved_sources"]) or "（空）"
        reasons = "; ".join(row["conflict_reasons"]) or "-"
        cited = ", ".join(row["citation"]["cited"]) or "无"
        valid = "无引用" if row["citation"]["valid"] is None else ("✅" if row["citation"]["valid"] else "❌")
        lines.append(
            f"| {row['id']} | {sources} | {'是' if row['conflict_flag'] else '否'} | {reasons} | {cited} | {valid} |"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-set", default=str(DEFAULT_EVAL_SET))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--mode", default="hybrid", choices=["vector", "hybrid"])
    parser.add_argument("--reuse-answers", action="store_true",
                        help="复用 reports/eval_generation.json 中的回答，只重算来源/冲突/引用")
    parser.add_argument("--input", default=str(ROOT / "reports" / "eval_generation.json"))
    args = parser.parse_args()

    if args.reuse_answers:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        results = payload["results"]
        cases = load_cases(Path(args.eval_set))
        meta = {case["id"]: case for case in cases}
        for row in results:
            case = meta.get(row["id"])
            if not case:
                continue
            row["expected_points"] = case.get("expected_points", [])
            row["should_refuse"] = bool(case.get("should_refuse"))
            row["category"] = case["category"]
            coverage, hits, refused = score_answer(row["answer"], row["expected_points"])
            row["coverage"] = round(coverage, 4)
            row["matched_points"] = hits
            row["refused"] = refused
            row["passed"] = refused if row["should_refuse"] else coverage >= 0.5
        results = recompute_flags(results, args.mode)
    else:
        cases = load_cases(Path(args.eval_set))
        if args.limit:
            cases = cases[: args.limit]
        results = evaluate(cases, args.mode)
    summary = summarize(results)
    json_path, md_path = write_report(results, summary, args.mode, Path(args.out_dir))

    print("\n=== summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nreport: {md_path}")
    print(f"details: {json_path}")


if __name__ == "__main__":
    main()
