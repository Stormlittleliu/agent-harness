# -*- coding: utf-8 -*-
"""自建任务集：跨分类单元抽样，直接跑现有 Harness。

任务集在 ``data/evals/datasets/selfbuilt/tasks.jsonl``，三种 kind：

- ``retrieval``：调 ``rag_retrieve``，按 ``expected_sources`` 算 Hit/MRR（能力层）
- ``single_turn``：跑一次 Agent，按 ``expected_points`` / ``expected_tools`` 判分（行为层）
- ``multi_turn``：同一 ``thread_id`` 连续多轮，按最后一轮回答 + 全轨迹工具判分

用法::

    python -m core.quality.selfbuilt --all
    python -m core.quality.selfbuilt --scenario robot_vacuum --trials 1
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.agent.framework import FrameworkAgent  # noqa: E402
from core.quality.agent_eval import extract_final_answer, extract_tool_calls  # noqa: E402
from core.quality.metrics import score_case, score_retrieval  # noqa: E402
from core.quality.paths import DATASETS_DIR, OUTPUTS_DIR  # noqa: E402
from core.quality.rag_harness import result_parts, sources_from_artifact  # noqa: E402
from core.scenarios.registry import get_scenario, list_scenarios  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

TASKS_PATH = DATASETS_DIR / "selfbuilt" / "tasks.jsonl"
OUT_DIR = OUTPUTS_DIR / "selfbuilt"
KINDS = ("retrieval", "single_turn", "multi_turn")


def load_tasks(path: Path | str = TASKS_PATH) -> list[dict]:
    tasks = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                tasks.append(json.loads(line))
    return tasks


def validate_tasks(tasks: list[dict], scenarios: set[str] | None = None) -> list[str]:
    """结构校验：不合法就不要浪费模型调用。"""
    known = scenarios if scenarios is not None else set(list_scenarios())
    errors: list[str] = []
    seen: set[str] = set()
    for task in tasks:
        task_id = str(task.get("id") or "")
        label = task_id or "<missing id>"
        if not task_id:
            errors.append("存在缺少 id 的任务")
        elif task_id in seen:
            errors.append(f"{label}: id 重复")
        seen.add(task_id)

        kind = task.get("kind")
        if kind not in KINDS:
            errors.append(f"{label}: kind 必须是 {KINDS} 之一，收到 {kind}")
        scenario = task.get("scenario")
        if scenario not in known:
            errors.append(f"{label}: 未知场景 {scenario}")
        if not str(task.get("cell") or "").strip():
            errors.append(f"{label}: 缺少 cell")

        if kind == "retrieval":
            if not task.get("question"):
                errors.append(f"{label}: retrieval 缺少 question")
            if not task.get("expected_sources"):
                errors.append(f"{label}: retrieval 缺少 expected_sources")
        elif kind == "single_turn":
            if not task.get("question"):
                errors.append(f"{label}: single_turn 缺少 question")
        elif kind == "multi_turn":
            turns = task.get("turns") or []
            if len(turns) < 2:
                errors.append(f"{label}: multi_turn 至少需要 2 轮")

        if kind in {"single_turn", "multi_turn"}:
            has_target = (
                task.get("expected_points")
                or task.get("expected_regex")
                or task.get("expected_tools")
                or task.get("should_refuse")
            )
            if not has_target:
                errors.append(f"{label}: 缺少 expected_points / expected_regex / expected_tools / should_refuse")
    return errors


def _score(task: dict, answer: str, tool_names: list[str]) -> dict:
    # 任务里可能省略这些字段；统一补成空列表，避免把 None 传进评分器。
    normalized = {
        **task,
        "expected_points": task.get("expected_points") or [],
        "expected_regex": task.get("expected_regex") or [],
        "expected_tools": task.get("expected_tools") or [],
    }
    result = score_case(normalized, answer, tool_names)
    return {
        "passed": result["passed"],
        "coverage": result["coverage"],
        "tools_ok": result["tools_ok"],
        "matched_points": result["matched_points"],
        "refused": result["refused"],
    }


def _rag_retrieve_tool():
    """检索类任务直接用 RAG 工具集的 rag_retrieve，不依赖场景有没有注册它。"""
    from core.tools.rag.tools import build_rag_tools

    return build_rag_tools(where={"domain": "robot"})[1]


def evaluate_task(agent: FrameworkAgent, task: dict, trial: int = 0, retrieval_tool=None) -> dict:
    kind = task["kind"]
    base = {"id": task["id"], "kind": kind, "cell": task.get("cell"), "trial": trial}

    if kind == "retrieval":
        tool = retrieval_tool or _rag_retrieve_tool()
        result = tool.invoke({
            "name": "rag_retrieve",
            "args": {"query": task["question"], "k": 4},
            "id": f"selfbuilt-{task['id']}",
            "type": "tool_call",
        })
        _, artifact = result_parts(result)
        sources = sources_from_artifact(artifact)
        hit, mrr = score_retrieval(sources, task.get("expected_sources", []))
        return {**base, "passed": bool(hit), "hit": bool(hit), "mrr": mrr, "sources": sources}

    if kind == "single_turn":
        state = agent.invoke(task["question"])
        messages = state.get("messages") or []
    else:
        thread_id = f"selfbuilt-{task['id']}-{trial}-{uuid.uuid4().hex[:8]}"
        state = {}
        for turn in task["turns"]:
            state = agent.invoke(turn, thread_id=thread_id)
        messages = state.get("messages") or []

    answer = extract_final_answer(messages)
    tool_names = [call["name"] for call in extract_tool_calls(messages) if call.get("name")]
    return {**base, "answer": answer, "tool_names": sorted(set(tool_names)), **_score(task, answer, tool_names)}


def summarize(results: list[dict], trials: int) -> dict:
    by_cell: dict[str, dict] = defaultdict(lambda: {"n": 0, "passed": 0})
    by_kind: dict[str, dict] = defaultdict(lambda: {"n": 0, "passed": 0})
    by_task: dict[str, list[bool]] = defaultdict(list)
    for row in results:
        by_cell[row["cell"]]["n"] += 1
        by_cell[row["cell"]]["passed"] += int(bool(row["passed"]))
        by_kind[row["kind"]]["n"] += 1
        by_kind[row["kind"]]["passed"] += int(bool(row["passed"]))
        by_task[row["id"]].append(bool(row["passed"]))

    pass_k = {task_id: all(flags) for task_id, flags in by_task.items()}
    return {
        "total": len(results),
        "passed": sum(int(bool(row["passed"])) for row in results),
        "trials": trials,
        "by_cell": dict(by_cell),
        "by_kind": dict(by_kind),
        "pass_k": sum(pass_k.values()),
        "task_count": len(pass_k),
        "failures": [row["id"] for row in results if not row["passed"]],
    }


def render_markdown(report: dict) -> str:
    summary = report["summary"]
    lines = [
        "# 自建任务集评测",
        "",
        f"> 时间：{report['timestamp']}｜任务 {summary['task_count']} 条｜trials {summary['trials']}",
        f"> 通过（按 trial）：{summary['passed']}/{summary['total']}｜pass^k：{summary['pass_k']}/{summary['task_count']}",
        "",
        "## 按分类单元",
        "",
        "| cell | 样本 | 通过 | 通过率 |",
        "|---|---:|---:|---:|",
    ]
    for cell, stat in sorted(summary["by_cell"].items()):
        rate = stat["passed"] / stat["n"] if stat["n"] else 0
        lines.append(f"| {cell} | {stat['n']} | {stat['passed']} | {rate:.1%} |")

    lines += ["", "## 按 kind", "", "| kind | 样本 | 通过 | 通过率 |", "|---|---:|---:|---:|"]
    for kind, stat in sorted(summary["by_kind"].items()):
        rate = stat["passed"] / stat["n"] if stat["n"] else 0
        lines.append(f"| {kind} | {stat['n']} | {stat['passed']} | {rate:.1%} |")

    lines += ["", "## 未通过", ""]
    if summary["failures"]:
        errors = {}
        for row in report.get("results", []):
            if row.get("error"):
                errors.setdefault(row["id"], row["error"])
        for task_id in summary["failures"]:
            detail = errors.get(task_id)
            lines.append(f"- `{task_id}`" + (f"：{detail}" if detail else ""))
    else:
        lines.append("（无）")
    return "\n".join(lines) + "\n"


def run(scenario: str | None = None, trials: int = 1, limit: int = 0, kind: str | None = None) -> dict:
    tasks = load_tasks()
    errors = validate_tasks(tasks)
    if errors:
        raise SystemExit("任务集不合法：\n" + "\n".join(errors))
    if scenario:
        tasks = [task for task in tasks if task["scenario"] == scenario]
    if kind:
        tasks = [task for task in tasks if task["kind"] == kind]
    if limit:
        tasks = tasks[:limit]
    if not tasks:
        raise SystemExit("没有匹配的任务")

    grouped: dict[str, list[dict]] = defaultdict(list)
    for task in tasks:
        grouped[task["scenario"]].append(task)

    retrieval_tool = _rag_retrieve_tool() if any(t["kind"] == "retrieval" for t in tasks) else None
    results: list[dict] = []
    for name, items in grouped.items():
        agent = FrameworkAgent(get_scenario(name))
        for task in items:
            for trial in range(trials):
                try:
                    rows = [evaluate_task(agent, task, trial, retrieval_tool)]
                except Exception as exc:  # noqa: BLE001 - 单条失败不影响整批
                    rows = [{
                        "id": task["id"], "kind": task["kind"], "cell": task.get("cell"),
                        "trial": trial, "passed": False, "error": f"{type(exc).__name__}: {exc}",
                    }]
                for row in rows:
                    results.append(row)
                    flag = "PASS" if row.get("passed") else "FAIL"
                    print(f"[{flag}] {row['id']} ({row['cell']})")

    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "summary": summarize(results, trials),
        "results": results,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = OUT_DIR / f"selfbuilt_{stamp}.json"
    md_path = OUT_DIR / f"selfbuilt_{stamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not scenario and not kind and not limit:
        # 只有全量运行才更新门禁基准，避免子集跑分被当成整体指标。
        (OUT_DIR / "selfbuilt_latest.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    markdown = render_markdown(report)
    md_path.write_text(markdown, encoding="utf-8")
    print(markdown)
    print(f"报告：{md_path}")
    return report


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="自建任务集评测")
    parser.add_argument("--scenario", help="只跑某个场景")
    parser.add_argument("--trials", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--kind", choices=KINDS, help="只跑某一类任务")
    parser.add_argument("--all", action="store_true", help="跑全部任务（默认）")
    args = parser.parse_args(argv)
    run(scenario=args.scenario, trials=args.trials, limit=args.limit, kind=args.kind)


if __name__ == "__main__":
    main()
