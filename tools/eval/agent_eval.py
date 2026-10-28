# -*- coding: utf-8 -*-
"""通用 Agent 测试运行器：只依赖 ReactAgent + Scenario 的 cases.jsonl。

不 import 任何具体业务工具；换场景只需要 --scenario。
"""
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.messages import AIMessage  # noqa: E402

from agent.react_agent import ReactAgent  # noqa: E402
from tools.eval.judge import build_judge, judge_answer  # noqa: E402
from tools.eval.metrics import score_case  # noqa: E402

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


def message_text(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content or "")


def extract_final_answer(messages) -> str:
    for message in reversed(messages):
        if not isinstance(message, AIMessage):
            continue
        text = message_text(message).strip()
        if text:
            return text
    return ""


def extract_tool_calls(messages) -> list[dict]:
    calls = []
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            if isinstance(call, dict):
                calls.append({"name": call.get("name", ""), "args": call.get("args", {})})
            else:
                calls.append({"name": getattr(call, "name", ""), "args": getattr(call, "args", {})})
    return calls


def run(scenario_name="robot_vacuum", case_id=None, limit=0, judge=False):
    agent = ReactAgent(scenario_name)
    scenario = agent.scenario
    cases_path = scenario.cases_path
    if not cases_path or not Path(cases_path).exists():
        raise FileNotFoundError(f"场景 {scenario_name} 没有测试用例文件：{cases_path}")

    cases = load_cases(Path(cases_path))
    if case_id:
        cases = [case for case in cases if case["id"] == case_id]
        if not cases:
            raise ValueError(f"找不到用例：{case_id}")
    if limit:
        cases = cases[:limit]

    judge_chain = build_judge() if judge else None
    results = []

    for index, case in enumerate(cases, 1):
        final_state = agent.framework.invoke(case["question"])
        messages = final_state["messages"]
        answer = extract_final_answer(messages)
        tool_calls = extract_tool_calls(messages)
        tool_names = [item["name"] for item in tool_calls if item.get("name")]

        deterministic = score_case(case, answer, tool_names)
        judged = None
        if judge_chain is not None:
            judged = judge_answer(
                judge_chain,
                case["question"],
                case.get("expected_points", []),
                bool(case.get("should_refuse")),
                tool_names,
                answer,
            )

        passed = deterministic["passed"]
        if judged is not None:
            passed = judged.get("verdict") == "pass"

        results.append({
            **case,
            "answer": answer,
            "tool_calls": tool_calls,
            "tool_names": tool_names,
            "coverage": deterministic["coverage"],
            "matched_points": deterministic["matched_points"],
            "tools_ok": deterministic["tools_ok"],
            "refused": deterministic["refused"],
            "passed": passed,
            "judge": judged,
        })
        print(
            f"[{index}/{len(cases)}] {case['id']} {case['category']} "
            f"coverage={deterministic['coverage']:.2f} tools={tool_names} pass={passed}"
        )

    summary = {
        "scenario": scenario_name,
        "total": len(results),
        "passed": sum(1 for row in results if row["passed"]),
        "by_category": dict(Counter(row["category"] for row in results)),
        "tool_cases_ok": sum(1 for row in results if row["tools_ok"]),
        "refusal_correct": sum(1 for row in results if row["should_refuse"] and row["refused"]),
        "refusal_count": sum(1 for row in results if row["should_refuse"]),
    }
    if judge:
        summary["judge_pass"] = sum(1 for row in results if (row["judge"] or {}).get("verdict") == "pass")

    out_dir = ROOT / "evals" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"agent_test_{scenario_name}_{stamp}.json"
    md_path = out_dir / f"agent_test_{scenario_name}_{stamp}.md"

    json_path.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(md_path, summary, results, judge)

    print("\n=== summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nreport: {md_path}")
    print(f"details: {json_path}")
    return summary


def write_markdown(path: Path, summary, results, judge):
    lines = [
        "# Agent 测试报告",
        "",
        f"- 场景：{summary['scenario']}",
        f"- 用例数：{summary['total']}",
        f"- 通过：{summary['passed']}/{summary['total']}",
        f"- 分类分布：{summary['by_category']}",
        f"- 拒答正确：{summary['refusal_correct']}/{summary['refusal_count']}",
    ]
    if judge:
        lines.append(f"- LLM judge 通过：{summary.get('judge_pass', 0)}/{summary['total']}")
    lines += [
        "",
        "| ID | 类别 | 问题 | 覆盖 | 工具 | 拒答 | 通过 | 回答摘要 |",
        "|:---|:---|:---|:---:|:---|:---:|:---:|:---|",
    ]
    for row in results:
        answer = row["answer"].replace("\n", " ").replace("|", "\\|")
        if len(answer) > 90:
            answer = answer[:90] + "..."
        tools = ", ".join(row["tool_names"]) or "-"
        lines.append(
            f"| {row['id']} | {row['category']} | {row['question']} | {row['coverage']:.0%} | "
            f"{tools} | {'是' if row['refused'] else '否'} | {'✅' if row['passed'] else '❌'} | {answer} |"
        )
    if judge:
        lines += ["", "## Judge 明细", "", "| ID | 判定 | 覆盖 | 理由 |", "|:---|:---|:---:|:---|"]
        for row in results:
            judged = row.get("judge") or {}
            reason = str(judged.get("reason", "")).replace("\n", " ").replace("|", "\\|")
            lines.append(
                f"| {row['id']} | {judged.get('verdict', '')} | "
                f"{float(judged.get('coverage', 0.0)):.0%} | {reason} |"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def list_cases(scenario_name="robot_vacuum"):
    agent = ReactAgent(scenario_name)
    cases = load_cases(Path(agent.scenario.cases_path))
    print(f"场景：{agent.scenario.name} — {agent.scenario.description}")
    for case in cases:
        print(f"  {case['id']:<20} [{case['category']}] {case['question']}")
    return cases


def interactive(scenario_name="robot_vacuum"):
    agent = ReactAgent(scenario_name)
    print(f"场景：{agent.scenario.name}（输入 exit 退出）")
    while True:
        try:
            query = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if query.lower() in {"exit", "quit", "q"}:
            break
        if not query:
            continue
        state = agent.framework.invoke(query)
        answer = extract_final_answer(state["messages"])
        tools = [item["name"] for item in extract_tool_calls(state["messages"])]
        print(f"Agent：{answer}")
        if tools:
            print(f"工具：{', '.join(tools)}")
