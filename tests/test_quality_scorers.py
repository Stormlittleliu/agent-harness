# -*- coding: utf-8 -*-
"""Scorer / Metric / Reducer 分层。"""
from core.quality import scorers
from core.quality.records import Score


def test_behavior_and_judge_scores():
    behavior = scorers.behavior_score(
        {"coverage": 0.75, "passed": True, "tools_ok": True, "refused": False,
         "matched_points": ["a", "b"]}
    )
    assert behavior.name == "behavior"
    assert behavior.value == 0.75
    assert behavior.passed is True
    assert behavior.metadata["matched_points"] == ["a", "b"]

    judge = scorers.judge_score({"verdict": "partial", "coverage": 0.5, "reason": "half"})
    assert judge is not None
    assert judge.name == "judge"
    assert judge.value == 0.5
    assert judge.passed is False


def test_outcome_score_requires_all_checks():
    score = scorers.outcome_score(
        [{"ok": True, "type": "file"}, {"ok": False, "type": "sqlite", "reason": "missing"}]
    )
    assert score.value == 0.5
    assert score.passed is False
    assert score.metadata["checks"][1]["reason"] == "missing"


def test_metrics_and_reducers():
    passed = [Score("behavior", 1.0, True), Score("behavior", 0.8, True)]
    mixed = [Score("behavior", 1.0, True), Score("behavior", 0.0, False)]

    assert scorers.mean([score.value for score in passed]) == 0.9
    assert scorers.pass_rate(passed) == 1.0
    assert scorers.defect_rate(mixed) == 0.5
    assert scorers.pass_at_least(passed, 2) is True
    assert scorers.pass_at_least(mixed, 2) is False
    assert scorers.pass_at_k(mixed, 2) is True

    reduced = scorers.reduce_by_case({"a": passed, "b": mixed}, k=2)
    assert reduced["a"]["pass^k"] is True
    assert reduced["b"]["pass^k"] is False
    assert reduced["b"]["pass@k"] is True
