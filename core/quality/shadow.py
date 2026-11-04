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
        return {"passed": result, "outcome": None, "tool_names": []}
    if isinstance(result, dict):
        outcome = None
        for score in result.get("scores") or []:
            if isinstance(score, dict) and score.get("name") == "outcome":
                outcome = bool(score.get("passed"))
        return {
            "passed": bool(result.get("passed")),
            "outcome": outcome,
            "tool_names": list(result.get("tool_names") or []),
            "tokens": int(result.get("tokens") or 0),
            "latency_ms": int(result.get("latency_ms") or 0),
        }
    return {
        "passed": bool(getattr(result, "passed", False)),
        "outcome": None,
        "tool_names": [],
        "tokens": 0,
        "latency_ms": 0,
    }


def _rate(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return round(sum(1 for row in rows if row[key]) / len(rows), 4)


def _outcome_rate(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [row[key] for row in rows if row.get(key) is not None]
    if not values:
        return None
    return round(sum(1 for value in values if value) / len(values), 4)


def _avg(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0.0
    return round(sum(float(row.get(key) or 0) for row in rows) / len(rows), 1)


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
    pattern_id: str = "",
    trials: int = 1,
) -> dict[str, Any]:
    """跑 baseline 与 candidate，写 ``outputs/shadow/<shadow_id>/shadow.json``。

    ``baseline`` / ``candidate`` 可以是 ``FrameworkAgent``，也可以是任何
    ``runner(agent, case)`` 能接受的对象。每条 case 跑 ``trials`` 次，
    用"全部 trial 通过"作为该 case 的 pass^k。返回值 ``decision=pending``。
    """
    runner = runner or _default_runner
    trials = max(1, int(trials or 1))
    cases = split_cases(cases, held_out_ratio=held_out_ratio, seed=seed)
    rows: list[dict[str, Any]] = []
    for case in cases:
        baseline_trials = [_row(runner(baseline, case)) for _ in range(trials)]
        candidate_trials = [_row(runner(candidate, case)) for _ in range(trials)]
        baseline_outcomes = [
            item["outcome"] for item in baseline_trials if item["outcome"] is not None
        ]
        candidate_outcomes = [
            item["outcome"] for item in candidate_trials if item["outcome"] is not None
        ]
        safety = bool((case.get("metadata") or {}).get("safety") or case.get("safety"))
        rows.append({
            "case_id": str(case.get("id") or case.get("case_id") or ""),
            "split": case.get("split", "train"),
            "safety": safety,
            "baseline_passed": all(item["passed"] for item in baseline_trials),
            "candidate_passed": all(item["passed"] for item in candidate_trials),
            "baseline_outcome": all(baseline_outcomes) if baseline_outcomes else None,
            "candidate_outcome": all(candidate_outcomes) if candidate_outcomes else None,
            "baseline_tools": baseline_trials[-1].get("tool_names") or [],
            "candidate_tools": candidate_trials[-1].get("tool_names") or [],
            "baseline_tokens": _avg(baseline_trials, "tokens"),
            "candidate_tokens": _avg(candidate_trials, "tokens"),
            "baseline_latency_ms": _avg(baseline_trials, "latency_ms"),
            "candidate_latency_ms": _avg(candidate_trials, "latency_ms"),
            "trials": trials,
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
    safety_regressions = [
        row["case_id"] for row in rows
        if row["safety"] and row["baseline_passed"] and not row["candidate_passed"]
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
        "pattern_id": pattern_id,
        "case_count": len(rows),
        "trials": trials,
        "held_out_count": len(held_out),
        "baseline": {
            "pass_k": baseline_rate,
            "k": trials,
            "pass_rate": baseline_rate,
            "train_pass_rate": _rate(train, "baseline_passed"),
            "held_out_pass_rate": _rate(held_out, "baseline_passed"),
            "outcome_rate": _outcome_rate(rows, "baseline_outcome"),
            "avg_tokens": _avg(rows, "baseline_tokens"),
            "avg_latency_ms": _avg(rows, "baseline_latency_ms"),
        },
        "candidate": {
            "pass_k": candidate_rate,
            "k": trials,
            "pass_rate": candidate_rate,
            "train_pass_rate": _rate(train, "candidate_passed"),
            "held_out_pass_rate": _rate(held_out, "candidate_passed"),
            "outcome_rate": _outcome_rate(rows, "candidate_outcome"),
            "avg_tokens": _avg(rows, "candidate_tokens"),
            "avg_latency_ms": _avg(rows, "candidate_latency_ms"),
        },
        "comparison": {
            "pass_rate_delta": round(candidate_rate - baseline_rate, 4),
            "pass_rate_ok": pass_rate_ok,
            "held_out_ok": held_out_ok,
            "regressions": regressions,
            "improvements": improvements,
            "safety_regressions": safety_regressions,
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
