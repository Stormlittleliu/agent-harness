# -*- coding: utf-8 -*-
"""行为评测的 3-trial 聚合测试（不调用模型）。"""
from core.quality import agent_eval
from core.quality.agent_eval import aggregate_trials, evaluate_cases, summarize_results


def test_aggregate_trials_pass_k_and_mean():
    case = {"id": "case-1"}
    rows = [
        {"id": "case-1", "passed": True, "trace_id": "t1", "category": "qa"},
        {"id": "case-1", "passed": True, "trace_id": "t2", "category": "qa"},
        {"id": "case-1", "passed": False, "trace_id": "t3", "category": "qa"},
    ]
    result = aggregate_trials(case, rows)
    assert result["passed"] is False
    assert result["pass_rate"] == 0.6667
    assert result["trial_passes"] == [True, True, False]
    assert result["trial_trace_ids"] == ["t1", "t2", "t3"]


def test_summarize_results_includes_trials_and_mean():
    results = [
        {"category": "qa", "passed": True, "pass_rate": 1.0, "tools_ok": True,
         "should_refuse": False, "refused": False},
        {"category": "qa", "passed": False, "pass_rate": 0.5, "tools_ok": True,
         "should_refuse": False, "refused": False},
    ]
    summary = summarize_results("demo", results, trials=3)
    assert summary["total"] == 2
    assert summary["passed"] == 1
    assert summary["trials"] == 3
    assert summary["mean_pass_rate"] == 0.75


def test_evaluate_cases_reports_each_trial(monkeypatch):
    def fake_case(agent, case, judge_chain):
        return {
            "id": case["id"],
            "category": "qa",
            "passed": True,
            "trace_id": "t",
            "scores": [{"name": "behavior", "value": 1.0, "passed": True}],
        }

    monkeypatch.setattr(agent_eval, "evaluate_case", fake_case)
    seen = []
    results = evaluate_cases(
        None,
        [{"id": "case-1", "category": "qa"}],
        trials=2,
        on_trial=lambda row: seen.append(row["trial"]),
    )
    assert seen == [1, 2]
    assert results[0]["pass_rate"] == 1.0
    assert results[0]["scores"][0]["name"] == "behavior"


def test_judge_cannot_override_deterministic_failure(monkeypatch):
    class FakeAgent:
        last_trace_id = "t"

        def invoke(self, question):
            return {"messages": []}

    monkeypatch.setattr(
        agent_eval,
        "score_case",
        lambda case, answer, tool_names: {
            "coverage": 0.0,
            "matched_points": [],
            "tools_ok": False,
            "refused": False,
            "passed": False,
        },
    )
    monkeypatch.setattr(agent_eval, "judge_answer", lambda *args: {"verdict": "pass"})
    row = agent_eval.evaluate_case(
        FakeAgent(), {"question": "q", "expected_points": []}, judge_chain=object()
    )
    assert row["passed"] is False
    assert row["judge_pass"] is True
