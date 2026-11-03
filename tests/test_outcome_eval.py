# -*- coding: utf-8 -*-
"""Outcome 断言的离线测试：文件 / SQLite / 任务图 / 路由。"""
import json
import sqlite3

from langchain_core.messages import ToolMessage

from core.quality import outcome_eval


def test_substitute_run_id_recurses():
    value = {"a": "{run_id}", "b": ["{run_id}-x"], "c": 1}
    assert outcome_eval.substitute_run_id(value, "r1") == {"a": "r1", "b": ["r1-x"], "c": 1}


def test_file_created_checks_new_file_content(tmp_path, monkeypatch):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "old.md").write_text("old", encoding="utf-8")
    before = outcome_eval.snapshot_files(notes)
    (notes / "new.md").write_text("Agent 评测要看 outcome", encoding="utf-8")
    monkeypatch.setattr(outcome_eval, "ROOT", tmp_path)

    spec = {
        "type": "file_created",
        "root": "notes",
        "glob": "*.md",
        "contains_all": ["outcome"],
    }
    result = outcome_eval.run_check(spec, {"before": {"notes": before}, "run_id": "r1"})
    assert result["ok"] is True
    assert result["path"] == "notes/new.md"


def test_file_created_rejects_missing_content(tmp_path, monkeypatch):
    notes = tmp_path / "notes"
    notes.mkdir()
    before = outcome_eval.snapshot_files(notes)
    (notes / "new.md").write_text("没有关键字", encoding="utf-8")
    monkeypatch.setattr(outcome_eval, "ROOT", tmp_path)

    spec = {"type": "file_created", "root": "notes", "glob": "*.md", "contains_all": ["outcome"]}
    result = outcome_eval.run_check(spec, {"before": {"notes": before}, "run_id": "r1"})
    assert result["ok"] is False
    assert "缺少内容" in result["reason"]


def test_sqlite_row_matches_value(tmp_path, monkeypatch):
    db = tmp_path / "memory.sqlite"
    connection = sqlite3.connect(db)
    connection.execute("CREATE TABLE memory (key TEXT, value TEXT)")
    connection.execute("INSERT INTO memory VALUES (?, ?)", ("memory-key-r1", "简洁、要点式"))
    connection.commit()
    connection.close()
    monkeypatch.setattr(outcome_eval, "ROOT", tmp_path)

    spec = {
        "type": "sqlite_row",
        "db": "memory.sqlite",
        "table": "memory",
        "match": {"key": "memory-key-{run_id}"},
        "expect": {"value": "简洁"},
    }
    result = outcome_eval.run_check(spec, {"run_id": "r1"})
    assert result["ok"] is True


def test_task_status_requires_completed(tmp_path, monkeypatch):
    db = tmp_path / "tasks.sqlite"
    connection = sqlite3.connect(db)
    connection.execute("CREATE TABLE tasks (subject TEXT, status TEXT)")
    connection.execute("INSERT INTO tasks VALUES (?, ?)", ("outcome-task-r1", "in_progress"))
    connection.commit()
    connection.close()
    monkeypatch.setattr(outcome_eval, "ROOT", tmp_path)

    spec = {
        "type": "task_status",
        "db": "tasks.sqlite",
        "table": "tasks",
        "subject_contains": "outcome-task-{run_id}",
        "status": "completed",
    }
    assert outcome_eval.run_check(spec, {"run_id": "r1"})["ok"] is False

    connection = sqlite3.connect(db)
    connection.execute("UPDATE tasks SET status = 'completed'")
    connection.commit()
    connection.close()
    assert outcome_eval.run_check(spec, {"run_id": "r1"})["ok"] is True


def test_router_target_checks_trace(monkeypatch):
    message = ToolMessage(
        content=json.dumps({"target": "workspace_assistant", "target_trace_id": "run-abc"}),
        name="route_to_workspace",
        tool_call_id="call-1",
    )
    monkeypatch.setattr(outcome_eval, "_trace_exists", lambda trace_id: trace_id == "run-abc")
    spec = {"type": "router_target", "target": "workspace_assistant", "require_trace": True}
    result = outcome_eval.run_check(spec, {"messages": [message], "run_id": "r1"})
    assert result["ok"] is True

    wrong = {"type": "router_target", "target": "research_assistant", "require_trace": True}
    assert outcome_eval.run_check(wrong, {"messages": [message], "run_id": "r1"})["ok"] is False


def test_aggregate_trials_pass_k_and_mean():
    case = {"id": "c1"}
    rows = [
        {"id": "c1", "passed": True, "run_id": "a", "checks": []},
        {"id": "c1", "passed": False, "run_id": "b", "checks": []},
    ]
    result = outcome_eval.aggregate_trials(case, rows)
    assert result["passed"] is False
    assert result["pass_rate"] == 0.5
    assert result["trial_passes"] == [True, False]
    assert result["trial_run_ids"] == ["a", "b"]
