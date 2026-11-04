# -*- coding: utf-8 -*-
"""M2 shadow：baseline/candidate 对比、held-out 标记、只记录不切换。"""
import json

from core.quality.shadow import run_shadow, split_cases


def _cases(count=6):
    return [{"id": f"case-{index}"} for index in range(1, count + 1)]


def _runner(baseline_fail=(), candidate_fail=()):
    def run(agent, case):
        failed = set(baseline_fail if agent == "baseline" else candidate_fail)
        return {"passed": case["id"] not in failed, "tool_names": [agent]}

    return run


def test_split_cases_is_deterministic_and_marks_both_sides():
    first = split_cases(_cases(), held_out_ratio=0.5, seed="s")
    second = split_cases(_cases(), held_out_ratio=0.5, seed="s")
    assert [case["split"] for case in first] == [case["split"] for case in second]
    assert {case["split"] for case in first} == {"train", "held_out"}
    assert sum(1 for case in first if case["split"] == "held_out") == 3


def test_shadow_records_regression_and_never_adopts(tmp_path):
    cases = _cases(6)
    result = run_shadow(
        "baseline",
        "candidate",
        cases,
        runner=_runner(baseline_fail=("case-1",), candidate_fail=("case-1", "case-2")),
        shadow_id="shadow-test",
        out_root=tmp_path / "shadow",
        held_out_ratio=0.5,
        scenario="demo",
    )

    assert result["case_count"] == 6
    assert result["comparison"]["regressions"] == ["case-2"]
    assert result["comparison"]["improvements"] == []
    assert result["candidate"]["pass_rate"] < result["baseline"]["pass_rate"]
    assert result["comparison"]["pass_rate_ok"] is False
    assert result["decision"] == "pending"

    payload = json.loads(
        (tmp_path / "shadow" / "shadow-test" / "shadow.json").read_text(encoding="utf-8")
    )
    assert payload["scenario"] == "demo"
    assert len(payload["results"]) == 6
    assert {row["split"] for row in payload["results"]} == {"train", "held_out"}
    # shadow 只写自己的目录，不碰 data/specs。
    assert not (tmp_path / "specs").exists()


def test_shadow_records_improvement(tmp_path):
    result = run_shadow(
        "baseline",
        "candidate",
        _cases(4),
        runner=_runner(baseline_fail=("case-1",), candidate_fail=()),
        shadow_id="shadow-improve",
        out_root=tmp_path,
        held_out_ratio=0.5,
    )
    assert result["comparison"]["improvements"] == ["case-1"]
    assert result["comparison"]["regressions"] == []
    assert result["comparison"]["pass_rate_ok"] is True
    assert result["decision"] == "pending"


def test_shadow_accepts_boolean_runner(tmp_path):
    result = run_shadow(
        "a",
        "b",
        _cases(2),
        runner=lambda agent, case: agent == "b",
        shadow_id="shadow-bool",
        out_root=tmp_path,
        held_out_ratio=0.5,
    )
    assert result["baseline"]["pass_rate"] == 0.0
    assert result["candidate"]["pass_rate"] == 1.0
    assert result["comparison"]["improvements"] == ["case-1", "case-2"]


def test_shadow_trials_use_pass_k_per_case(tmp_path):
    def runner(agent, case):
        return {"passed": not (agent == "candidate" and case["id"] == "case-1")}

    result = run_shadow(
        "baseline",
        "candidate",
        _cases(4),
        runner=runner,
        shadow_id="shadow-trials",
        out_root=tmp_path,
        held_out_ratio=0.5,
        trials=3,
    )
    assert result["trials"] == 3
    assert result["candidate"]["pass_k"] == 0.75
    assert result["candidate"]["k"] == 3


def test_shadow_collects_outcome_cost_and_safety(tmp_path):
    def runner(agent, case):
        return {
            "passed": not (agent == "candidate" and case["id"] == "case-2"),
            "scores": [{"name": "outcome", "passed": agent == "baseline"}],
            "tokens": 100 if agent == "baseline" else 200,
            "latency_ms": 1000,
        }

    cases = _cases(3)
    cases[1] = {**cases[1], "safety": True}
    result = run_shadow(
        "baseline",
        "candidate",
        cases,
        runner=runner,
        shadow_id="shadow-cost",
        out_root=tmp_path,
        held_out_ratio=0.0,
    )
    assert result["baseline"]["outcome_rate"] == 1.0
    assert result["candidate"]["outcome_rate"] == 0.0
    assert result["baseline"]["avg_tokens"] == 100.0
    assert result["candidate"]["avg_tokens"] == 200.0
    assert result["comparison"]["safety_regressions"] == ["case-2"]


def test_shadow_held_out_gate(tmp_path):
    # baseline 全过、candidate 只挂一个 held-out case 时，held_out_ok 必须为 False。
    cases = split_cases(_cases(4), held_out_ratio=0.5, seed="shadow")
    held_out = next(case["id"] for case in cases if case["split"] == "held_out")
    result = run_shadow(
        "baseline",
        "candidate",
        _cases(4),
        runner=_runner(baseline_fail=(), candidate_fail=(held_out,)),
        shadow_id="shadow-held-out",
        out_root=tmp_path,
        held_out_ratio=0.5,
        seed="shadow",
    )
    assert result["comparison"]["held_out_ok"] is False
