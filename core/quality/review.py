# -*- coding: utf-8 -*-
"""评测结果复核：LLM judge + 人工标注，落在同一个 JSONL 里。

流程：

1. ``build``：读 ``outputs/selfbuilt/*.json``，把每条结果整理成复核行，
   可选跑 LLM judge（同义改写、拒答、要点覆盖）；
2. 人工用 ``app_review.py`` 扫一遍，标 pass / fail / unsure；
3. ``summarize`` 给出 auto / judge / human 三方一致率与分歧清单。

复核文件写到 ``outputs/selfbuilt/review_<runid>.jsonl``，一行一条，可直接 diff。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.quality.paths import DATASETS_DIR, OUTPUTS_DIR  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

TASKS_PATH = DATASETS_DIR / "selfbuilt" / "tasks.jsonl"
REVIEW_DIR = OUTPUTS_DIR / "selfbuilt"
LABELS = ("pass", "fail", "unsure")
ISSUES = (
    "检索未召回",
    "工具没调对",
    "要点词不匹配",
    "回答错误",
    "拒答不当",
    "运行错误",
    "其他",
)


def load_tasks(path: Path | str = TASKS_PATH) -> dict[str, dict]:
    tasks = {}
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                task = json.loads(line)
                tasks[task["id"]] = task
    return tasks


def _question_of(task: dict, result: dict) -> str:
    if task.get("kind") == "multi_turn":
        return " → ".join(task.get("turns") or [])
    return str(result.get("question") or task.get("question") or "")


def build_review(run_path: Path | str, use_judge: bool = True) -> list[dict]:
    run_path = Path(run_path)
    run = json.loads(run_path.read_text(encoding="utf-8"))
    tasks = load_tasks()
    chain = None
    if use_judge:
        from core.quality.judge import build_judge

        chain = build_judge()

    rows: list[dict] = []
    for result in run.get("results", []):
        task = tasks.get(result.get("id"), {})
        row = {
            "key": f"{result.get('id')}@{result.get('trial', 0)}",
            "task_id": result.get("id"),
            "trial": result.get("trial", 0),
            "cell": result.get("cell") or task.get("cell"),
            "kind": result.get("kind") or task.get("kind"),
            "scenario": task.get("scenario"),
            "question": _question_of(task, result),
            "expected_points": task.get("expected_points") or [],
            "expected_tools": task.get("expected_tools") or [],
            "expected_sources": task.get("expected_sources") or [],
            "answer": result.get("answer") or "",
            "tool_names": result.get("tool_names") or [],
            "sources": result.get("sources") or [],
            "auto": {
                "passed": bool(result.get("passed")),
                "coverage": result.get("coverage"),
                "tools_ok": result.get("tools_ok"),
                "error": result.get("error"),
            },
            "judge": None,
            "human": None,
        }
        if chain is not None and row["kind"] != "retrieval" and not result.get("error"):
            from core.quality.judge import judge_answer

            verdict = judge_answer(
                chain,
                row["question"],
                row["expected_points"],
                bool(task.get("should_refuse")),
                row["tool_names"],
                row["answer"],
            )
            row["judge"] = {
                "verdict": verdict.get("verdict"),
                "coverage": verdict.get("coverage"),
                "covered": verdict.get("covered"),
                "missing": verdict.get("missing"),
                "reason": verdict.get("reason"),
            }
        rows.append(row)
    return rows


def save_review(rows: list[dict], path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return path


def load_review(path: Path | str) -> list[dict]:
    rows = []
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def set_label(
    rows: list[dict],
    key: str,
    label: str | None,
    note: str = "",
    issue: str | None = None,
) -> bool:
    """写人工结论。``label=None`` 表示清除；``issue`` 是问题类型（见 ISSUES）。"""
    if label is not None and label not in LABELS:
        raise ValueError(f"label 必须是 {LABELS} 之一")
    if issue is not None and issue not in ISSUES:
        raise ValueError(f"issue 必须是 {ISSUES} 之一")
    for row in rows:
        if row["key"] == key:
            row["human"] = (
                None
                if label is None
                else {
                    "label": label,
                    "issue": issue,
                    "note": note,
                    "at": datetime.now().isoformat(timespec="seconds"),
                }
            )
            return True
    return False


def _judge_pass(row: dict) -> bool | None:
    judge = row.get("judge") or {}
    verdict = judge.get("verdict")
    if verdict == "pass":
        return True
    if verdict in {"fail", "partial"}:
        return False
    return None


def summarize(rows: list[dict]) -> dict:
    total = len(rows)
    auto_pass = sum(1 for row in rows if row["auto"]["passed"])
    judged = [row for row in rows if row.get("judge")]
    judge_pass = sum(1 for row in judged if _judge_pass(row))
    labeled = [row for row in rows if row.get("human")]
    human_pass = sum(1 for row in labeled if row["human"]["label"] == "pass")

    disagreements = []
    for row in judged:
        judge = _judge_pass(row)
        if judge is not None and judge != bool(row["auto"]["passed"]):
            disagreements.append(row["key"])

    human_disagreements = []
    for row in labeled:
        human = row["human"]["label"]
        if human == "unsure":
            continue
        want = human == "pass"
        if want != bool(row["auto"]["passed"]):
            human_disagreements.append(row["key"])

    return {
        "total": total,
        "auto_pass": auto_pass,
        "judged": len(judged),
        "judge_pass": judge_pass,
        "labeled": len(labeled),
        "human_pass": human_pass,
        "unlabeled": total - len(labeled),
        "auto_vs_judge_disagreements": disagreements,
        "auto_vs_human_disagreements": human_disagreements,
    }


def render_summary(report: dict) -> str:
    lines = [
        "# 复核汇总",
        "",
        f"- 总数：{report['total']}",
        f"- 自动判分通过：{report['auto_pass']}",
        f"- judge 通过：{report['judge_pass']} / 已判 {report['judged']}",
        f"- 人工标注：{report['labeled']}（通过 {report['human_pass']}），未标 {report['unlabeled']}",
        f"- auto vs judge 分歧：{len(report['auto_vs_judge_disagreements'])}",
        f"- auto vs human 分歧：{len(report['auto_vs_human_disagreements'])}",
    ]
    for title, keys in (
        ("auto vs judge", report["auto_vs_judge_disagreements"]),
        ("auto vs human", report["auto_vs_human_disagreements"]),
    ):
        if keys:
            lines += ["", f"## {title}", ""] + [f"- `{key}`" for key in keys]
    return "\n".join(lines) + "\n"


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="自建集复核：judge + 人工标注")
    sub = parser.add_subparsers(dest="cmd", required=True)

    build = sub.add_parser("build", help="从评测结果生成复核文件")
    build.add_argument("--run", required=True)
    build.add_argument("--no-judge", action="store_true")
    build.add_argument("--out")

    show = sub.add_parser("show", help="打印复核汇总")
    show.add_argument("--review", required=True)

    args = parser.parse_args(argv)
    if args.cmd == "build":
        rows = build_review(args.run, use_judge=not args.no_judge)
        run_id = Path(args.run).stem.replace("selfbuilt_", "")
        out = Path(args.out) if args.out else REVIEW_DIR / f"review_{run_id}.jsonl"
        save_review(rows, out)
        print(f"复核文件：{out}（{len(rows)} 条）")
        print(render_summary(summarize(rows)))
    else:
        print(render_summary(summarize(load_review(args.review))))


if __name__ == "__main__":
    main()
