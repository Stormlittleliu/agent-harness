# -*- coding: utf-8 -*-
"""结构化输出评测：读取 create_agent 的 structured_response，而不是解析自然语言。

用法：
    python -m core.quality.structured_eval --limit 5
    python -m core.quality.structured_eval --case structured-office-001
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pydantic import BaseModel, ValidationError  # noqa: E402

from core.agent.framework import FrameworkAgent  # noqa: E402
from core.quality.agent_eval import extract_final_answer, load_cases  # noqa: E402
from core.quality.metrics import normalize  # noqa: E402
from core.quality.paths import STRUCTURED_OUT  # noqa: E402
from core.scenarios.registry import get_scenario  # noqa: E402
from core.scenarios.structured_demo.schema import ReportSchema  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def extract_report(state: dict) -> tuple[ReportSchema | None, str | None]:
    """把 struct_response 归一成 ReportSchema；失败时返回可读原因。"""
    raw = state.get("structured_response")
    if raw is None:
        return None, "structured_response 缺失（模型没有按 schema 返回）"
    if isinstance(raw, ReportSchema):
        return raw, None
    if isinstance(raw, BaseModel):
        data = raw.model_dump()
    elif isinstance(raw, dict):
        data = raw
    else:
        return None, f"structured_response 类型不支持：{type(raw).__name__}"
    try:
        return ReportSchema.model_validate(data), None
    except ValidationError as exc:
        return None, str(exc)


def evaluate_case(agent: FrameworkAgent, case: dict) -> dict:
    state = agent.invoke(case["question"])
    report, schema_error = extract_report(state)
    expected_points = case.get("expected_points", [])
    matched: list[str] = []
    coverage = 0.0
    evidence_ok = False
    confidence_ok = False
    actions_ok = False

    if report is not None:
        text = json.dumps(report.model_dump(), ensure_ascii=False)
        text_norm = normalize(text)
        matched = [point for point in expected_points if normalize(point) in text_norm]
        coverage = len(matched) / len(expected_points) if expected_points else 1.0
        evidence_ok = len(report.evidence) >= int(case.get("min_evidence", 1))
        confidence_ok = report.confidence >= float(case.get("min_confidence", 0.0))
        actions_ok = len(report.next_actions) >= 1

    passed = bool(
        report is not None
        and coverage >= 0.5
        and evidence_ok
        and confidence_ok
        and actions_ok
    )

    return {
        **case,
        "answer": report.summary if report is not None else extract_final_answer(state.get("messages", [])),
        "schema_ok": report is not None,
        "schema_error": schema_error,
        "confidence": report.confidence if report is not None else None,
        "evidence_count": len(report.evidence) if report is not None else 0,
        "actions_count": len(report.next_actions) if report is not None else 0,
        "matched_points": matched,
        "coverage": round(coverage, 4),
        "evidence_ok": evidence_ok,
        "confidence_ok": confidence_ok,
        "actions_ok": actions_ok,
        "passed": passed,
        "trace_id": getattr(agent, "last_trace_id", None),
    }


def summarize_results(scenario_name: str, results: list[dict]) -> dict:
    confidences = [row["confidence"] for row in results if row["confidence"] is not None]
    return {
        "scenario": scenario_name,
        "total": len(results),
        "passed": sum(1 for row in results if row["passed"]),
        "schema_ok": sum(1 for row in results if row["schema_ok"]),
        "avg_confidence": round(sum(confidences) / len(confidences), 4) if confidences else 0.0,
        "avg_evidence": round(
            sum(row["evidence_count"] for row in results) / len(results), 2
        ) if results else 0.0,
        "by_category": dict(Counter(row["category"] for row in results)),
    }


def write_markdown(path: Path, summary: dict, results: list[dict]) -> None:
    lines = [
        "# 结构化输出评测",
        "",
        f"- 场景：{summary['scenario']}",
        f"- 用例数：{summary['total']}",
        f"- 通过：{summary['passed']}/{summary['total']}",
        f"- schema 合法：{summary['schema_ok']}/{summary['total']}",
        f"- 平均置信度：{summary['avg_confidence']:.2f}",
        f"- 平均证据条数：{summary['avg_evidence']:.1f}",
        "",
        "| ID | 类别 | schema | 证据 | 置信度 | 覆盖 | 通过 | 摘要 |",
        "|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|",
    ]
    for row in results:
        answer = str(row["answer"]).replace("\n", " ").replace("|", "\\|")[:90]
        lines.append(
            f"| {row['id']} | {row['category']} | {'✅' if row['schema_ok'] else '❌'} | "
            f"{row['evidence_count']} | {row['confidence'] if row['confidence'] is not None else '—'} | "
            f"{row['coverage']:.0%} | {'✅' if row['passed'] else '❌'} | {answer} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(scenario_name="structured_demo", case_id=None, limit=0, out_dir=None):
    agent = FrameworkAgent(get_scenario(scenario_name))
    cases_path = agent.scenario.cases_path
    if not cases_path or not Path(cases_path).exists():
        raise FileNotFoundError(f"场景 {scenario_name} 没有测试用例文件：{cases_path}")

    cases = load_cases(Path(cases_path))
    if case_id:
        cases = [case for case in cases if case["id"] == case_id]
        if not cases:
            raise ValueError(f"找不到用例：{case_id}")
    if limit:
        cases = cases[:limit]

    results = []
    for index, case in enumerate(cases, 1):
        result = evaluate_case(agent, case)
        results.append(result)
        print(
            f"[{index}/{len(cases)}] {result['id']} schema={result['schema_ok']} "
            f"coverage={result['coverage']:.2f} pass={result['passed']}"
        )

    summary = summarize_results(scenario_name, results)
    out = Path(out_dir) if out_dir else STRUCTURED_OUT
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out / f"structured_test_{scenario_name}_{stamp}.json"
    md_path = out / f"structured_test_{scenario_name}_{stamp}.md"
    json_path.write_text(
        json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(md_path, summary, results)

    print("\n=== summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nreport: {md_path}")
    print(f"details: {json_path}")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description="结构化输出评测")
    parser.add_argument("--scenario", default="structured_demo")
    parser.add_argument("--case")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--out-dir")
    args = parser.parse_args(argv)
    run(args.scenario, args.case, args.limit, args.out_dir)


if __name__ == "__main__":
    main()
