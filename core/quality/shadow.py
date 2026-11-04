# -*- coding: utf-8 -*-
"""候选工作流 shadow：baseline 与 candidate 各跑一遍，只记录，不切换（M2）。

shadow 的职责边界：

- 不写 ``data/specs``、不改 ``active.json``、不换线上场景；
- baseline / candidate 用同一批 cases，并标出 train / held_out；
- 记录 pass 情况、回归、改进和 held-out 表现；
- ``decision`` 永远是 ``pending``——采纳是 M3 的人工门槛。

真正的模型调用由 ``runner`` 提供，默认用 ``agent_eval.evaluate_case``；
测试可以注入一个确定的 runner，不需要模型。
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from core.quality.paths import OUTPUTS_DIR

SHADOW_VERSION = 1
Runner = Callable[[Any, dict[str, Any]], dict[str, Any]]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def split_cases(
    cases: list[dict[str, Any]],
    *,
    held_out_ratio: float = 0.3,
    seed: str = "shadow",
) -> list[dict[str, Any]]:
    """确定性地给 cases 标 train / held_out。

    按 ``sha1(seed:case_id)`` 排序，前 ``round(n * ratio)`` 条做 held-out。
    不用随机数：同一批 cases 每次 shadow 的分组一致，结果可对比。
    """
    if not cases:
        return []
    ratio = min(max(float(held_out_ratio), 0.0), 1.0)
    ordered = sorted(
        cases,
        key=lambda case: hashlib.sha1(
            f"{seed}:{case.get('id') or case.get('case_id') or ''}".encode("utf-8")
        ).hexdigest(),
    )
    count = round(len(cases) * ratio)
    if len(cases) >= 2:
        count = min(max(count, 1), len(cases) - 1)
    held_out = {
        id(case) for case in ordered[:count]
    }
    return [
        {**case, "split": "held_out" if id(case) in held_out else "train"}
        for case in cases
    ]


def _default_runner(agent: Any, case: dict[str, Any]) -> dict[str, Any]:
    from core.quality.agent_eval import evaluate_case

    row = evaluate_case(agent, case)
    return {
        "passed": bool(row.get("passed")),
        "tool_names": list(row.get("tool_names") or []),
    }


def _row(result: Any) -> dict[str, Any]:
    if isinstance(result, bool):
        return {"passed": result}
    if isinstance(result, dict):
        return {
            "passed": bool(result.get("passed")),
            "tool_names": list(result.get("tool_names") or []),
        }
    return {"passed": bool(getattr(result, "passed", False)), "tool_names": []}


def _rate(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return round(sum(1 for row in rows if row[key]) / len(rows), 4)


def run_shadow(
    baseline: Any,
    candidate: Any,
    cases: list[dict[str, Any]],
    *,
    runner: Runner | None = None,
    shadow_id: str | None = None,
    out_root: Path | str | None = None,
    held_out_ratio: float = 0.3,
    seed: str = "shadow",
    scenario: str = "",
) -> dict[str, Any]:
    """跑 baseline 与 candidate，写 ``outputs/shadow/<shadow_id>/shadow.json``。

    ``baseline`` / ``candidate`` 可以是 ``FrameworkAgent``，也可以是任何
    ``runner(agent, case)`` 能接受的对象。返回值包含对比与 ``decision=pending``。
    """
    runner = runner or _default_runner
    cases = split_cases(cases, held_out_ratio=held_out_ratio, seed=seed)
    rows: list[dict[str, Any]] = []
    for case in cases:
        baseline_result = _row(runner(baseline, case))
        candidate_result = _row(runner(candidate, case))
        rows.append({
            "case_id": str(case.get("id") or case.get("case_id") or ""),
            "split": case.get("split", "train"),
            "baseline_passed": baseline_result["passed"],
            "candidate_passed": candidate_result["passed"],
            "baseline_tools": baseline_result.get("tool_names") or [],
            "candidate_tools": candidate_result.get("tool_names") or [],
        })

    held_out = [row for row in rows if row["split"] == "held_out"]
    train = [row for row in rows if row["split"] == "train"]
    regressions = [
        row["case_id"] for row in rows
        if row["baseline_passed"] and not row["candidate_passed"]
    ]
    improvements = [
        row["case_id"] for row in rows
        if row["candidate_passed"] and not row["baseline_passed"]
    ]
    baseline_rate = _rate(rows, "baseline_passed")
    candidate_rate = _rate(rows, "candidate_passed")
    held_out_ok = _rate(held_out, "candidate_passed") >= _rate(held_out, "baseline_passed")
    pass_rate_ok = candidate_rate >= baseline_rate

    shadow_id = shadow_id or f"shadow-{datetime.now():%Y%m%d-%H%M%S}"
    result = {
        "shadow_version": SHADOW_VERSION,
        "shadow_id": shadow_id,
        "created_at": _now(),
        "scenario": scenario,
        "case_count": len(rows),
        "held_out_count": len(held_out),
        "baseline": {
            "pass_rate": baseline_rate,
            "train_pass_rate": _rate(train, "baseline_passed"),
            "held_out_pass_rate": _rate(held_out, "baseline_passed"),
        },
        "candidate": {
            "pass_rate": candidate_rate,
            "train_pass_rate": _rate(train, "candidate_passed"),
            "held_out_pass_rate": _rate(held_out, "candidate_passed"),
        },
        "comparison": {
            "pass_rate_delta": round(candidate_rate - baseline_rate, 4),
            "pass_rate_ok": pass_rate_ok,
            "held_out_ok": held_out_ok,
            "regressions": regressions,
            "improvements": improvements,
        },
        "decision": "pending",  # 永不自动采纳；M3 人工门槛
        "results": rows,
    }

    out_dir = Path(out_root) if out_root is not None else OUTPUTS_DIR / "shadow"
    target = out_dir / shadow_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "shadow.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    result["out_dir"] = target.as_posix()
    return result
