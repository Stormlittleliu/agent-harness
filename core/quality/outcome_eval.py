# -*- coding: utf-8 -*-
"""Outcome 评测：检查 Agent 运行后的真实环境状态，而不是回答文本。

支持的断言：
- file_created / file_exists：workspace 笔记、research 报告、coding 产物/运行日志；
- sqlite_row：workspace MemoryStore 的长期偏好；
- task_status：coding 任务图的 subject/status；
- router_target：router 工具返回的 target 与 target_trace_id。

用法：
    python -m core.quality.runner outcome --scenario workspace_assistant --trials 3
    python -m core.quality.runner outcome --all --trials 3
"""
from __future__ import annotations

import fnmatch
import json
import re
import sqlite3
import sys
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.messages import ToolMessage  # noqa: E402

from core.agent.framework import FrameworkAgent  # noqa: E402
from core.agent.workflow import WorkflowRuntime  # noqa: E402
from core.quality.agent_eval import extract_final_answer  # noqa: E402
from core.quality.paths import OUTCOME_OUT, TRACE_OUT  # noqa: E402
from core.scenarios.registry import get_scenario  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

OUTCOME_SCENARIOS = (
    "workspace_assistant",
    "research_assistant",
    "coding_demo",
    "router",
)
_AGENTS: dict[str, FrameworkAgent] = {}


def load_outcome_cases(path: Path) -> list[dict]:
    cases = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def substitute_run_id(value: Any, run_id: str) -> Any:
    if isinstance(value, str):
        return value.replace("{run_id}", run_id)
    if isinstance(value, list):
        return [substitute_run_id(item, run_id) for item in value]
    if isinstance(value, dict):
        return {key: substitute_run_id(item, run_id) for key, item in value.items()}
    return value


def snapshot_files(root: Path) -> set[str]:
    root = Path(root)
    if not root.exists():
        return set()
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _message_text(message) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content or "")


def _content_ok(text: str, spec: dict) -> tuple[bool, str]:
    for needle in spec.get("contains_all", []) or []:
        if needle not in text:
            return False, f"缺少内容：{needle}"
    contains_any = spec.get("contains_any", []) or []
    if contains_any and not any(needle in text for needle in contains_any):
        return False, f"未命中任一内容：{contains_any}"
    at_least = spec.get("contains_at_least")
    if at_least:
        items = at_least.get("items", [])
        minimum = int(at_least.get("min", 1))
        matched = [item for item in items if item in text]
        if len(matched) < minimum:
            return False, f"命中 {len(matched)}/{len(items)}，要求至少 {minimum}"
    pattern = spec.get("regex")
    if pattern and not re.search(pattern, text):
        return False, f"正则未命中：{pattern}"
    return True, ""


def _matching_new_files(spec: dict, before: set[str], run_id: str) -> list[Path]:
    root = ROOT / spec["root"]
    pattern = substitute_run_id(spec.get("glob", "*"), run_id)
    current = snapshot_files(root)
    return [
        root / relative
        for relative in sorted(current - before)
        if fnmatch.fnmatch(relative, pattern)
    ]


def check_file_created(spec: dict, ctx: dict) -> dict:
    root = ROOT / spec["root"]
    before = ctx["before"].get(spec["root"], set())
    candidates = _matching_new_files(spec, before, ctx["run_id"])
    if not candidates:
        return {
            "ok": False,
            "type": "file_created",
            "reason": f"{spec['root']} 下没有新增文件（glob={spec.get('glob', '*')}）",
        }
    errors = []
    for path in candidates:
        ok, reason = _content_ok(_read_text(path), spec)
        if ok:
            return {
                "ok": True,
                "type": "file_created",
                "path": path.relative_to(ROOT).as_posix(),
            }
        errors.append(f"{path.name}: {reason}")
    return {
        "ok": False,
        "type": "file_created",
        "reason": "新增文件内容不满足：" + "；".join(errors[:3]),
        "candidates": [path.relative_to(ROOT).as_posix() for path in candidates[:5]],
    }


def check_file_exists(spec: dict, ctx: dict) -> dict:
    path = ROOT / spec["root"] / substitute_run_id(spec["path"], ctx["run_id"])
    if not path.exists():
        return {"ok": False, "type": "file_exists", "reason": f"文件不存在：{path.relative_to(ROOT)}"}
    ok, reason = _content_ok(_read_text(path), spec)
    return {
        "ok": ok,
        "type": "file_exists",
        "path": path.relative_to(ROOT).as_posix(),
        "reason": "" if ok else reason,
    }


def _query_rows(db_path: Path, table: str) -> list[dict]:
    if not Path(db_path).exists():
        return []
    connection = sqlite3.connect(str(db_path), timeout=5)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(f"SELECT * FROM {table}").fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def _row_matches(row: dict, spec: dict, run_id: str) -> bool:
    for column, expected in (spec.get("match") or {}).items():
        expected = substitute_run_id(expected, run_id)
        if expected not in str(row.get(column, "")):
            return False
    for column, expected in (spec.get("expect") or {}).items():
        expected = substitute_run_id(expected, run_id)
        if expected not in str(row.get(column, "")):
            return False
    return True


def check_sqlite_row(spec: dict, ctx: dict) -> dict:
    db_path = ROOT / spec["db"]
    rows = _query_rows(db_path, spec["table"])
    for row in rows:
        if _row_matches(row, spec, ctx["run_id"]):
            return {"ok": True, "type": "sqlite_row", "row": row}
    return {
        "ok": False,
        "type": "sqlite_row",
        "reason": f"{spec['db']}#{spec['table']} 没有满足条件的行",
        "rows": len(rows),
    }


def check_task_status(spec: dict, ctx: dict) -> dict:
    db_path = ROOT / spec["db"]
    rows = _query_rows(db_path, spec.get("table", "tasks"))
    subject = substitute_run_id(spec.get("subject_contains", ""), ctx["run_id"])
    expected_status = spec.get("status", "completed")
    for row in rows:
        if subject in str(row.get("subject", "")) and row.get("status") == expected_status:
            return {"ok": True, "type": "task_status", "task": row}
    return {
        "ok": False,
        "type": "task_status",
        "reason": f"没有 subject 含 {subject!r} 且 status={expected_status} 的任务",
        "rows": len(rows),
    }


def _trace_exists(trace_id: str) -> bool:
    if not trace_id:
        return False
    for path in sorted(Path(TRACE_OUT).glob("trace_*.jsonl")):
        try:
            with path.open(encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    if trace_id in line:
                        return True
        except OSError:
            continue
    return False


def check_router_target(spec: dict, ctx: dict) -> dict:
    last = None
    for message in ctx.get("messages", []):
        if not isinstance(message, ToolMessage):
            continue
        if not str(message.name or "").startswith("route_to_"):
            continue
        text = _message_text(message)
        try:
            payload = json.loads(text)
        except (TypeError, ValueError):
            continue
        if isinstance(payload, dict):
            last = payload
    if last is None:
        return {"ok": False, "type": "router_target", "reason": "没有找到 route_to_* 的工具结果"}
    target = last.get("target")
    trace_id = last.get("target_trace_id")
    expected = spec.get("target")
    if target != expected:
        return {
            "ok": False,
            "type": "router_target",
            "reason": f"target={target!r}，期望 {expected!r}",
        }
    if spec.get("require_trace", True) and not _trace_exists(str(trace_id or "")):
        return {
            "ok": False,
            "type": "router_target",
            "reason": f"target_trace_id={trace_id!r} 在 trace 文件中不存在",
        }
    return {"ok": True, "type": "router_target", "target": target, "trace_id": trace_id}


CHECKERS = {
    "file_created": check_file_created,
    "file_exists": check_file_exists,
    "sqlite_row": check_sqlite_row,
    "task_status": check_task_status,
    "router_target": check_router_target,
}


def run_check(spec: dict, ctx: dict) -> dict:
    checker = CHECKERS.get(spec.get("type"))
    if checker is None:
        return {"ok": False, "type": spec.get("type"), "reason": f"未知 check 类型：{spec.get('type')}"}
    try:
        return checker(spec, ctx)
    except Exception as exc:  # noqa: BLE001 - 单条断言失败不拖垮整轮评测
        return {
            "ok": False,
            "type": spec.get("type"),
            "reason": f"{type(exc).__name__}: {exc}",
        }


def _agent(scenario_name: str) -> FrameworkAgent:
    agent = _AGENTS.get(scenario_name)
    if agent is None:
        agent = FrameworkAgent(get_scenario(scenario_name))
        _AGENTS[scenario_name] = agent
    return agent


def evaluate_case(scenario_name: str, case: dict, trial: int) -> dict:
    run_id = f"out{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
    question = substitute_run_id(case["question_template"], run_id)
    checks = substitute_run_id(case.get("checks", []), run_id)

    before: dict[str, set[str]] = {}
    for spec in checks:
        if spec.get("type") == "file_created":
            root = spec["root"]
            before.setdefault(root, snapshot_files(ROOT / root))

    executor = case.get("executor", "agent")
    workflow_name = case.get("workflow")
    final_state = None
    messages: list = []
    answer = ""
    trace_id = None

    if executor == "workflow":
        scenario = get_scenario(scenario_name)
        runtime = WorkflowRuntime(scenario)
        final_state = runtime.run(workflow_name, question)
        answer = str(
            final_state.get("answer")
            or final_state.get("report")
            or final_state.get("draft")
            or final_state.get("summary")
            or ""
        )
    else:
        agent = _agent(scenario_name)
        final_state = agent.invoke(question)
        messages = final_state.get("messages", [])
        answer = extract_final_answer(messages)
        trace_id = getattr(agent, "last_trace_id", None)

    ctx = {"before": before, "messages": messages, "run_id": run_id, "scenario": scenario_name}
    check_results = [run_check(spec, ctx) for spec in checks]

    return {
        "id": case["id"],
        "category": case.get("category", "outcome"),
        "question": question,
        "run_id": run_id,
        "trial": trial,
        "executor": executor,
        "workflow": workflow_name,
        "answer": answer,
        "trace_id": trace_id,
        "checks": check_results,
        "passed": all(item["ok"] for item in check_results),
    }


def aggregate_trials(case: dict, rows: list[dict]) -> dict:
    trial_passes = [bool(row["passed"]) for row in rows]
    result = dict(rows[-1])
    result.update({
        "id": case["id"],
        "passed": all(trial_passes),
        "pass_rate": round(sum(trial_passes) / len(trial_passes), 4),
        "trial_passes": trial_passes,
        "trial_run_ids": [row["run_id"] for row in rows],
        "trials": len(trial_passes),
    })
    return result


def evaluate_cases(scenario_name: str, cases: list[dict], trials: int = 1, progress=None) -> list[dict]:
    trials = max(1, int(trials or 1))
    results = []
    for index, case in enumerate(cases, 1):
        rows = [evaluate_case(scenario_name, case, trial) for trial in range(1, trials + 1)]
        result = aggregate_trials(case, rows)
        results.append(result)
        if progress is not None:
            progress(index, len(cases), result)
    return results


def summarize_results(scenario_name: str, results: list[dict], trials: int = 1) -> dict:
    checks = [check for row in results for check in row.get("checks", [])]
    return {
        "scenario": scenario_name,
        "total": len(results),
        "passed": sum(1 for row in results if row["passed"]),
        "trials": max(1, int(trials or 1)),
        "mean_pass_rate": round(
            sum(float(row.get("pass_rate", 1.0 if row["passed"] else 0.0)) for row in results) / len(results), 4
        ) if results else 0.0,
        "checks_total": len(checks),
        "checks_ok": sum(1 for check in checks if check["ok"]),
        "by_type": dict(Counter(check["type"] for check in checks)),
    }


def write_markdown(path: Path, summary: dict, results: list[dict]) -> None:
    lines = [
        "# Outcome 评测报告",
        "",
        f"- 场景：{summary['scenario']}",
        f"- 用例数：{summary['total']}",
        f"- 通过（pass^k）：{summary['passed']}/{summary['total']}",
        f"- trials：{summary['trials']}",
        f"- mean pass rate：{summary['mean_pass_rate']:.4f}",
        f"- 断言：{summary['checks_ok']}/{summary['checks_total']} 通过",
        "",
        "| ID | pass^k | mean | 断言 | 失败原因 |",
        "|:---|:---:|:---:|:---|:---|",
    ]
    for row in results:
        failed = [check for check in row.get("checks", []) if not check["ok"]]
        reason = "；".join(str(check.get("reason", "")) for check in failed)[:160]
        lines.append(
            f"| {row['id']} | {'✅' if row['passed'] else '❌'} | {row.get('pass_rate', 0):.2f} | "
            f"{sum(1 for check in row.get('checks', []) if check['ok'])}/{len(row.get('checks', []))} | {reason or '-'} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _print_result(index, total, row):
    failed = [check for check in row.get("checks", []) if not check["ok"]]
    reason = "；".join(str(check.get("reason", "")) for check in failed)[:120]
    print(
        f"[{index}/{total}] {row['id']} pass^k={row['passed']} "
        f"mean={row.get('pass_rate', 0):.2f} {reason}"
    )


def run(
    scenario_name: str | None = None,
    trials: int = 3,
    case_id: str | None = None,
    all_scenarios: bool = False,
) -> dict:
    scenarios = list(OUTCOME_SCENARIOS) if all_scenarios else [scenario_name or "workspace_assistant"]
    OUTCOME_OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = {"summaries": {}, "results": {}}

    for name in scenarios:
        scenario = get_scenario(name)
        cases_path = Path(scenario.cases_path).with_name("outcome_cases.jsonl") if scenario.cases_path else None
        if cases_path is None or not cases_path.exists():
            print(f"[skip] {name} 没有 outcome_cases.jsonl")
            continue
        cases = load_outcome_cases(cases_path)
        if case_id:
            cases = [case for case in cases if case["id"] == case_id]
            if not cases:
                raise ValueError(f"找不到 outcome 用例：{case_id}")
        results = evaluate_cases(name, cases, trials=trials, progress=_print_result)
        summary = summarize_results(name, results, trials=trials)
        payload["summaries"][name] = summary
        payload["results"][name] = results

        json_path = OUTCOME_OUT / f"outcome_test_{name}_{stamp}.json"
        md_path = OUTCOME_OUT / f"outcome_test_{name}_{stamp}.md"
        json_path.write_text(
            json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        write_markdown(md_path, summary, results)
        print(f"\n{name}: {summary['passed']}/{summary['total']} pass^k, "
              f"mean={summary['mean_pass_rate']:.2f}")
        print(f"report: {md_path}")

    if all_scenarios:
        combined_json = OUTCOME_OUT / f"outcome_all_{stamp}.json"
        payload["total"] = sum(item["total"] for item in payload["summaries"].values())
        payload["passed"] = sum(item["passed"] for item in payload["summaries"].values())
        combined_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        combined_md = OUTCOME_OUT / f"outcome_all_{stamp}.md"
        lines = ["# Outcome 评测总览", "", "| 场景 | pass^k | mean | 断言 |", "|:---|:---:|:---:|:---|"]
        for name, summary in payload["summaries"].items():
            lines.append(
                f"| {name} | {summary['passed']}/{summary['total']} | "
                f"{summary['mean_pass_rate']:.2f} | {summary['checks_ok']}/{summary['checks_total']} |"
            )
        combined_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\ncombined: {combined_md}")

    return payload
