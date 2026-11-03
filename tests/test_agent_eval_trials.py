# -*- coding: utf-8 -*-
"""行为评测的 3-trial 聚合测试（不调用模型）。"""
from core.quality.agent_eval import aggregate_trials, summarize_results


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
