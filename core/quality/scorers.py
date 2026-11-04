# -*- coding: utf-8 -*-
"""评分、指标与 reducer 的最小分层。

借 Inspect AI 的 ``Scorer / Metric / Reducer`` 三分，但只保留 Python 里有用的部分：

- Scorer：把一次判定转成统一 ``Score``；
- Metric：对一组 ``Score`` 求 mean / pass_rate / defect_rate；
- Reducer：跨 trial 聚合，典型是 ``pass^k``。

不做 registry、不做可变 TaskState；调用方显式传数据。
"""
from __future__ import annotations

from typing import Callable, Iterable, Sequence

from core.quality.records import Score


def behavior_score(deterministic: dict) -> Score:
    """确定性行为评分（关键词 / 工具 / 拒答）→ Score。"""
    coverage = float(deterministic.get("coverage") or 0.0)
    passed = bool(deterministic.get("passed"))
    return Score(
        name="behavior",
        value=coverage,
        passed=passed,
        reason=(
            f"coverage={coverage:.2f} tools_ok={bool(deterministic.get('tools_ok'))} "
            f"refused={bool(deterministic.get('refused'))}"
        ),
        metadata={
            "matched_points": list(deterministic.get("matched_points") or []),
            "tools_ok": bool(deterministic.get("tools_ok")),
            "refused": bool(deterministic.get("refused")),
        },
    )


def judge_score(judged: dict | None) -> Score | None:
    """LLM judge 结果 → Score；没跑 judge 时返回 None。"""
    if judged is None:
        return None
    verdict = str(judged.get("verdict") or "").lower()
    passed = verdict == "pass"
    value = 1.0 if passed else (0.5 if verdict == "partial" else 0.0)
    return Score(
        name="judge",
        value=value,
        passed=passed,
        reason=str(judged.get("reason") or ""),
        metadata={
            "verdict": verdict,
            "coverage": float(judged.get("coverage") or 0.0),
            "missing": list(judged.get("missing") or []),
        },
    )


def outcome_score(checks: Sequence[dict]) -> Score:
    """Outcome 断言列表 → 一个总体 Score。

    单条 check 可以是 ``{"ok": bool, "type": str, "reason": str}``。
    """
    checks = list(checks or [])
    passed_count = sum(1 for check in checks if check.get("ok"))
    total = len(checks)
    passed = bool(total) and passed_count == total
    return Score(
        name="outcome",
        value=round(passed_count / total, 4) if total else 0.0,
        passed=passed,
        reason=f"{passed_count}/{total} checks passed",
        metadata={
            "checks": [
                {
                    "ok": bool(check.get("ok")),
                    "type": str(check.get("type") or ""),
                    "reason": str(check.get("reason") or ""),
                }
                for check in checks
            ]
        },
    )


def mean(values: Iterable[float]) -> float:
    values = [float(value) for value in values]
    return round(sum(values) / len(values), 4) if values else 0.0


def pass_rate(scores: Iterable[Score]) -> float:
    scores = list(scores)
    return round(sum(1 for score in scores if score.passed) / len(scores), 4) if scores else 0.0


def defect_rate(scores: Iterable[Score]) -> float:
    return round(1.0 - pass_rate(scores), 4)


def pass_at_least(scores: Iterable[Score], k: int) -> bool:
    """跨 trial reducer：k 次全部通过。空列表或不足 k 次返回 False。"""
    k = max(1, int(k))
    values = list(scores)[:k]
    return len(values) >= k and all(score.passed for score in values)


def pass_at_k(scores: Iterable[Score], k: int) -> bool:
    """k 次中至少一次通过（pass@k），与 pass^k 区分。"""
    k = max(1, int(k))
    return any(score.passed for score in list(scores)[:k])


def reduce_by_case(
    trial_scores: dict[str, Sequence[Score]],
    *,
    k: int = 1,
) -> dict[str, dict[str, float | bool]]:
    """按 case 聚合；返回 pass^k 与 mean。"""
    k = max(1, int(k))
    result: dict[str, dict[str, float | bool]] = {}
    for case_id, scores in trial_scores.items():
        scores = list(scores)
        result[case_id] = {
            "pass^k": pass_at_least(scores, k),
            "pass@k": pass_at_k(scores, k),
            "mean": mean(score.value for score in scores),
            "trials": len(scores),
        }
    return result


def scorer_chain(*scorers: Callable[[dict], Score | None]) -> Callable[[dict], list[Score]]:
    """把多个 scorer 串成一个；None 结果自动跳过。"""

    def run(payload: dict) -> list[Score]:
        scores: list[Score] = []
        for scorer in scorers:
            score = scorer(payload)
            if score is not None:
                scores.append(score)
        return scores

    return run
