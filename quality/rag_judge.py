# -*- coding: utf-8 -*-
"""RAG 生成结果复核：LLM-as-judge。

输入 outputs/rag/eval_generation.json，输出 <prefix>_judged.json/md。
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.output_parsers import StrOutputParser  # noqa: E402
from langchain_core.prompts import ChatPromptTemplate  # noqa: E402

from quality.paths import RAG_OUT  # noqa: E402
from model.factory import chat_model  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

JUDGE_PROMPT = """你是严格的 RAG 评测员。只依据【期望要点】和【检索上下文】判断【模型回答】，不要使用外部知识。

【问题】
{question}

【期望要点】
{points}

【是否应拒答】
{should_refuse}

【检索来源】
{sources}

【检索上下文】
{context}

【模型回答】
{answer}

请输出严格 JSON：
{{
  "covered": ["已覆盖的要点"],
  "missing": ["未覆盖的要点"],
  "coverage": 0.0,
  "refusal_correct": false,
  "grounded": false,
  "used_sources": ["真正支持回答的检索来源"],
  "verdict": "pass|partial|fail",
  "reason": "一句话说明"
}}

规则：
1. 允许同义改写，只要语义等价就算覆盖。
2. 数字、单位、否定条件必须一致。
3. 期望要点中出现“A 或 B”时，回答覆盖其中任意一个即可。
4. 如果【是否应拒答】为“是”：只要回答明确说明资料中没有相关信息，且没有给出具体政策/流程/时效/价格/联系方式，就算正确拒答（refusal_correct=true，coverage=1，verdict=pass）。不要求回答里出现“不编造”字样。
5. grounded：回答是否完全由【检索上下文】支持；used_sources 从【检索来源】中选，拒答时可为空。
6. 只输出 JSON，不要 Markdown 代码块。"""


def parse_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no json object found")
    return json.loads(text[start:end + 1])


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(RAG_OUT / "eval_generation.json"))
    parser.add_argument("--out-dir", default=str(RAG_OUT))
    parser.add_argument("--prefix", default="eval_generation")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    results = payload["results"]
    if args.limit:
        results = results[:args.limit]

    prompt = ChatPromptTemplate.from_template(JUDGE_PROMPT)
    chain = prompt | chat_model | StrOutputParser()

    judged = []
    errors = 0
    for index, row in enumerate(results, 1):
        try:
            raw = chain.invoke({
                "question": row["question"],
                "points": "\n".join(f"- {item}" for item in row.get("expected_points", [])) or "（无）",
                "should_refuse": "是" if row.get("should_refuse") else "否",
                "sources": "\n".join(f"- {item}" for item in row.get("retrieved_sources", [])) or "（无）",
                "context": row.get("retrieved_context", "（无）"),
                "answer": row["answer"],
            })
            verdict = parse_json(raw)
        except Exception as exc:  # noqa: BLE001
            errors += 1
            verdict = {
                "covered": row.get("matched_points", []),
                "missing": [],
                "coverage": row.get("coverage", 0.0),
                "refusal_correct": row.get("refused", False),
                "grounded": False,
                "used_sources": [],
                "verdict": "fail",
                "reason": f"judge error: {exc}",
            }
        merged = dict(row)
        merged["judge"] = verdict
        judged.append(merged)
        print(f"[{index}/{len(results)}] {row['id']} {verdict.get('verdict')} coverage={verdict.get('coverage')}")

    answer_rows = [row for row in judged if not row.get("should_refuse")]
    refusal_rows = [row for row in judged if row.get("should_refuse")]

    def source_valid(row):
        used = row["judge"].get("used_sources") or []
        retrieved = set(row.get("retrieved_sources", []))
        return all(item in retrieved for item in used)

    summary = {
        "total": len(judged),
        "by_category": dict(Counter(row["category"] for row in judged)),
        "answer_avg_coverage": round(
            sum(float(row["judge"].get("coverage", 0.0)) for row in answer_rows) / len(answer_rows), 4
        ) if answer_rows else 0.0,
        "answer_pass": sum(1 for row in answer_rows if row["judge"].get("verdict") == "pass"),
        "answer_partial": sum(1 for row in answer_rows if row["judge"].get("verdict") == "partial"),
        "answer_count": len(answer_rows),
        "answer_grounded": sum(1 for row in answer_rows if row["judge"].get("grounded")),
        "source_valid": sum(1 for row in answer_rows if source_valid(row)),
        "refusal_correct": sum(1 for row in refusal_rows if row["judge"].get("refusal_correct")),
        "refusal_count": len(refusal_rows),
        "passed": sum(1 for row in judged if row["judge"].get("verdict") == "pass"),
        "judge_errors": errors,
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{args.prefix}_judged.json"
    md_path = out_dir / f"{args.prefix}_judged.md"
    json_path.write_text(json.dumps({"summary": summary, "results": judged}, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# RAG 生成层评测（LLM-as-judge）",
        "",
        f"- 样本总数：{summary['total']}",
        f"- 答案题平均覆盖：{summary['answer_avg_coverage']:.2%}",
        f"- 答案题 pass / partial / 总数：{summary['answer_pass']} / {summary['answer_partial']} / {summary['answer_count']}",
        f"- 答案题 grounded：{summary['answer_grounded']}/{summary['answer_count']}",
        f"- 来源校验通过：{summary['source_valid']}/{summary['answer_count']}",
        f"- 拒答正确：{summary['refusal_correct']}/{summary['refusal_count']}",
        f"- 总体 pass：{summary['passed']}/{summary['total']}",
        f"- judge 解析失败：{summary['judge_errors']}",
        "",
        "> judge 与被测模型同为 deepseek-chat，存在自我偏好；关键 case 需人工复核。",
        "",
        "| ID | 类别 | 问题 | 覆盖 | 判定 | grounded | 使用来源 | 理由 |",
        "|:---|:---|:---|:---:|:---:|:---:|:---|:---|",
    ]
    for row in judged:
        judge = row["judge"]
        reason = str(judge.get("reason", "")).replace("\n", " ").replace("|", "\\|")
        used = ", ".join(judge.get("used_sources") or []) or "-"
        lines.append(
            f"| {row['id']} | {row['category']} | {row['question']} | "
            f"{float(judge.get('coverage', 0.0)):.0%} | {judge.get('verdict', '')} | "
            f"{'是' if judge.get('grounded') else '否'} | {used} | {reason} |"
        )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n=== summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {md_path}")
    print(f"details: {json_path}")


if __name__ == "__main__":
    main()
