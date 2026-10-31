# -*- coding: utf-8 -*-
from core.experiments.trigger_rate import count_triggers, summarize


def test_count_triggers_separates_subagent_and_task():
    result = count_triggers(["read_file", "subagent", "create_task", "list_tasks", "glob"])
    assert result["subagent"] == 1
    assert result["task"] == 2
    assert result["any"] == 3


def test_summarize_trigger_rates():
    rows = [
        {"subagent_calls": 0, "task_calls": 0, "any_trigger": False, "tool_names": ["read_file"]},
        {"subagent_calls": 1, "task_calls": 0, "any_trigger": True, "tool_names": ["subagent"]},
        {"subagent_calls": 0, "task_calls": 2, "any_trigger": True, "tool_names": ["create_task", "complete_task"]},
    ]
    summary = summarize(rows)
    assert summary["total"] == 3
    assert summary["subagent_runs"] == 1
    assert summary["task_runs"] == 1
    assert summary["any_trigger_runs"] == 2
    assert summary["subagent_rate"] == 0.3333
    assert summary["task_rate"] == 0.3333
    assert summary["avg_tools"] == 1.33
