# -*- coding: utf-8 -*-
"""自建任务集：结构校验与汇总逻辑（不调用模型）。"""
from core.quality import selfbuilt
from core.quality.selfbuilt import (
    KINDS,
    _score,
    load_tasks,
    render_markdown,
    summarize,
    validate_tasks,
)

SCENARIOS = {
    "robot_vacuum",
    "workspace_assistant",
    "research_assistant",
    "coding_demo",
    "router",
}


def test_task_file_loads_and_is_valid():
    tasks = load_tasks()
    assert len(tasks) >= 20
    assert validate_tasks(tasks, scenarios=SCENARIOS) == []
    assert {task["kind"] for task in tasks} <= set(KINDS)


def test_task_file_covers_multiple_cells():
    tasks = load_tasks()
    cells = {task["cell"] for task in tasks}
    assert "单轮×检索" in cells
    assert "单轮×文本" in cells
    assert "多轮×文本" in cells
    assert len(cells) >= 5


def test_multi_turn_tasks_have_scripts():
    for task in load_tasks():
        if task["kind"] == "multi_turn":
            assert len(task["turns"]) >= 2
            assert all(turn.strip() for turn in task["turns"])


def _task(**overrides):
    base = {
        "id": "x",
        "kind": "single_turn",
        "cell": "单轮×文本",
        "scenario": "robot_vacuum",
        "question": "q",
        "expected_points": ["p"],
    }
    base.update(overrides)
    return base


def test_validate_rejects_duplicate_id():
    errors = validate_tasks([_task(), _task()], scenarios=SCENARIOS)
    assert any("id 重复" in error for error in errors)


def test_validate_rejects_unknown_kind_and_scenario():
    errors = validate_tasks(
        [_task(kind="nope"), _task(id="y", scenario="ghost")], scenarios=SCENARIOS
    )
    assert any("kind" in error for error in errors)
    assert any("未知场景" in error for error in errors)


def test_validate_rejects_retrieval_without_sources():
    errors = validate_tasks(
        [_task(id="r", kind="retrieval", expected_points=None)], scenarios=SCENARIOS
    )
    assert any("expected_sources" in error for error in errors)


def test_validate_rejects_single_turn_multi_turn_without_turns():
    errors = validate_tasks(
        [_task(id="m", kind="multi_turn", turns=["only one"], expected_points=["p"])],
        scenarios=SCENARIOS,
    )
    assert any("至少需要 2 轮" in error for error in errors)


def test_validate_rejects_missing_target():
    errors = validate_tasks(
        [_task(expected_points=None)], scenarios=SCENARIOS
    )
    assert any("缺少 expected_points" in error for error in errors)


def test_score_matches_points_and_tools():
    task = _task(expected_points=["pass^k"], expected_tools=["search_notes"])
    result = _score(task, "评测要看 pass^k 和成本", ["search_notes"])
    assert result["passed"] is True
    assert result["coverage"] == 1.0

    missed = _score(task, "不知道", ["search_notes"])
    assert missed["passed"] is False


def test_score_refusal_case():
    task = _task(expected_points=None, should_refuse=True, expected_tools=[])
    assert _score(task, "资料中没有相关说明，无法确定。", [])["passed"] is True
    assert _score(task, "当然可以退。", [])["passed"] is False


def test_summarize_pass_k():
    results = [
        {"id": "a", "cell": "c1", "kind": "single_turn", "passed": True},
        {"id": "a", "cell": "c1", "kind": "single_turn", "passed": True},
        {"id": "b", "cell": "c2", "kind": "multi_turn", "passed": False},
    ]
    summary = summarize(results, trials=2)
    assert summary["task_count"] == 2
    assert summary["pass_k"] == 1
    assert summary["by_cell"]["c1"] == {"n": 2, "passed": 2}
    assert summary["failures"] == ["b"]


def test_render_markdown_contains_summary():
    report = {
        "timestamp": "2026-11-03T22:00:00",
        "summary": summarize(
            [{"id": "a", "cell": "c1", "kind": "single_turn", "passed": True}], trials=1
        ),
        "results": [],
    }
    text = render_markdown(report)
    assert "自建任务集评测" in text
    assert "pass^k" in text
    assert "c1" in text


class _FakeFixture:
    def __init__(self, source_id: str):
        self.id = f"selfbuilt-{source_id}"
        self.metadata = {"source_id": source_id}


def _fixture_row() -> dict:
    return {
        "passed": True,
        "answer": "评测要看 pass^k",
        "calls": [{"name": "search_notes", "args": {"query": "评测"}}],
        "coverage": 1.0,
        "matched_points": ["pass^k"],
        "any_tools_ok": True,
        "call_count_ok": True,
        "variant": "clean",
        "fixture_status": "ok",
    }


def test_run_single_turn_uses_task_fixture(monkeypatch, tmp_path):
    tasks = [_task(id="s1", kind="single_turn", scenario="robot_vacuum")]
    monkeypatch.setattr(selfbuilt, "load_tasks", lambda: tasks)
    monkeypatch.setattr(
        selfbuilt,
        "build_selfbuilt_fixtures",
        lambda scenario=None: [_FakeFixture("s1")],
    )
    monkeypatch.setattr(selfbuilt, "run_fixture", lambda fixture: _fixture_row())
    monkeypatch.setattr(selfbuilt, "OUT_DIR", tmp_path)

    report = selfbuilt.run(trials=1)
    row = report["results"][0]
    assert row["id"] == "s1"
    assert row["passed"] is True
    assert row["tool_names"] == ["search_notes"]
    assert row["fixture_variant"] == "clean"
    assert report["summary"]["passed"] == 1


def test_run_retrieval_keeps_rag_path(monkeypatch, tmp_path):
    tasks = [{
        "id": "r1",
        "kind": "retrieval",
        "cell": "单轮×检索",
        "scenario": "robot_vacuum",
        "question": "q",
        "expected_sources": ["a.txt"],
    }]
    monkeypatch.setattr(selfbuilt, "load_tasks", lambda: tasks)
    monkeypatch.setattr(selfbuilt, "_rag_retrieve_tool", lambda: object())
    monkeypatch.setattr(
        selfbuilt,
        "evaluate_task",
        lambda agent, task, trial, tool: {
            "id": task["id"],
            "kind": "retrieval",
            "cell": task["cell"],
            "trial": trial,
            "passed": True,
            "hit": True,
            "mrr": 1.0,
            "sources": ["a.txt"],
        },
    )
    monkeypatch.setattr(
        selfbuilt,
        "build_selfbuilt_fixtures",
        lambda **_: (_ for _ in ()).throw(AssertionError("retrieval 不应构建 fixture")),
    )
    monkeypatch.setattr(selfbuilt, "OUT_DIR", tmp_path)

    report = selfbuilt.run(trials=1)
    assert report["results"][0]["id"] == "r1"
    assert report["summary"]["by_kind"]["retrieval"]["passed"] == 1


def test_limit_applies_before_kind_split(monkeypatch, tmp_path):
    tasks = [
        {
            "id": "r1",
            "kind": "retrieval",
            "cell": "单轮×检索",
            "scenario": "robot_vacuum",
            "question": "q",
            "expected_sources": ["a.txt"],
        },
        _task(id="s1", kind="single_turn", scenario="robot_vacuum"),
    ]
    monkeypatch.setattr(selfbuilt, "load_tasks", lambda: tasks)
    monkeypatch.setattr(selfbuilt, "_rag_retrieve_tool", lambda: object())
    monkeypatch.setattr(
        selfbuilt,
        "evaluate_task",
        lambda agent, task, trial, tool: {
            "id": task["id"],
            "kind": "retrieval",
            "cell": task["cell"],
            "trial": trial,
            "passed": True,
        },
    )
    monkeypatch.setattr(
        selfbuilt,
        "build_selfbuilt_fixtures",
        lambda **_: (_ for _ in ()).throw(AssertionError("limit=1 时只应跑 retrieval")),
    )
    monkeypatch.setattr(selfbuilt, "OUT_DIR", tmp_path)

    report = selfbuilt.run(limit=1)
    assert [row["id"] for row in report["results"]] == ["r1"]
