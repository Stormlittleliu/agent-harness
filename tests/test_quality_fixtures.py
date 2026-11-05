# -*- coding: utf-8 -*-
"""任务级 fixture：工具桩、变体构造、判分，不调模型。"""
import json

from core.benchmarks.schema import BenchTask
from core.quality import fixtures as fixtures_module
from core.quality.fixtures import (
    ToolStub,
    _args_match,
    _normalize_schema,
    build_bfcl_fixtures,
    build_permission_fixtures,
    build_selfbuilt_fixtures,
    render_markdown,
    score_fixture,
    summarize,
)


def _task(name: str, expected: str, args: dict) -> BenchTask:
    return BenchTask(
        id=f"bfcl-{name}",
        source="bfcl-v4",
        source_version="x",
        split="test",
        category="tool_calling_simple",
        task_type="single_turn_tool",
        instruction=f"call {expected}",
        grader="code",
        environment={"kind": "bfcl"},
        tools=[{
            "name": expected,
            "description": f"{expected} tool",
            "parameters": {
                "type": "object",
                "properties": {key: {"type": "number"} for key in args},
                "required": list(args),
            },
        }],
        success_criteria=[{"type": "function_call", "name": expected, "args": args}],
    )


def test_tool_stub_records_call_and_raises():
    stub = ToolStub(name="calc", parameters={"type": "object", "properties": {}})
    tool = stub.build()
    tool.invoke({"name": "calc", "args": {"x": 1}, "id": "1", "type": "tool_call"})
    assert stub.calls == [{"x": 1}]

    broken = ToolStub(name="calc2", error="boom")
    try:
        broken.build().invoke({"name": "calc2", "args": {}, "id": "2", "type": "tool_call"})
    except RuntimeError as exc:
        assert "boom" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_args_match_accepts_bfcl_single_value_lists():
    assert _args_match({"base": [10]}, {"base": 10})
    assert _args_match({"base": [10]}, {"base": [10]})
    assert not _args_match({"base": [10]}, {"base": 11})
    assert _args_match({"polynomial": [[3.0, 2.0, -4.0]]}, {"polynomial": [3, 2, -4]})


def test_normalize_schema_handles_bfcl_dict_type():
    schema = _normalize_schema({"type": "dict", "properties": {"x": {"type": "int"}}})
    assert schema["type"] == "object"
    assert schema["properties"]["x"]["type"] == "integer"


def test_bfcl_fixtures_cover_four_variants():
    tasks = [
        _task("a", "calc_a", {"x": 1}),
        _task("b", "calc_b", {"y": 2}),
        _task("c", "calc_c", {"z": 3}),
    ]
    fixtures = build_bfcl_fixtures(tasks, limit=1, distractors=2)
    assert [fixture.variant for fixture in fixtures] == [
        "clean",
        "distractor",
        "missing",
        "failure",
    ]
    clean, distractor, missing, failure = fixtures
    assert len(clean.tools) == 1
    assert "unit" not in clean.expected["calls"][0]["args"]
    assert len(distractor.tools) == 3
    assert distractor.expected["no_calls"]
    assert missing.expected["calls"] == []
    assert failure.tools[0].error


def test_score_fixture_detects_forbidden_call():
    tasks = [_task("a", "calc_a", {"x": 1}), _task("b", "calc_b", {"y": 2})]
    fixture = build_bfcl_fixtures(tasks, limit=1, distractors=1)[1]
    calls = [{"name": "calc_a", "args": {"x": 1}}, {"name": "calc_b", "args": {}}]
    result = score_fixture(fixture, calls, answer="", status="ok")
    assert not result["passed"]
    assert result["forbidden_calls"] == ["calc_b"]


def test_permission_fixtures_use_hitl():
    fixtures = build_permission_fixtures()
    assert {fixture.variant for fixture in fixtures} == {
        "permission_approve",
        "permission_reject",
    }
    reject = next(fixture for fixture in fixtures if fixture.variant == "permission_reject")
    assert reject.high_risk_tools == {"reset_device": True}
    assert reject.expected["no_calls"] == ["reset_device"]

    result = score_fixture(reject, [], "已拒绝，未执行", status="rejected")
    assert result["passed"]

    approve = next(fixture for fixture in fixtures if fixture.variant == "permission_approve")
    result = score_fixture(
        approve,
        [{"name": "reset_device", "args": {"device_id": "SN-1001"}}],
        "已重置",
        status="approved",
    )
    assert result["passed"]


def test_summarize_groups_by_variant_and_renders_failures():
    rows = [
        {"id": "a", "variant": "clean", "passed": True, "status": "ok"},
        {"id": "b", "variant": "missing", "passed": False, "status": "ok", "answer": "25"},
    ]
    summary = summarize(rows)
    assert summary["passed"] == 1
    assert summary["by_variant"]["clean"] == {"passed": 1, "total": 1}
    assert summary["by_variant"]["missing"] == {"passed": 0, "total": 1}
    markdown = render_markdown(summary, "bfcl")
    assert "| missing | 0 | 1 |" in markdown
    assert "b" in markdown


def test_selfbuilt_fixtures_cover_all_scenarios():
    fixtures = build_selfbuilt_fixtures(scenario="all")
    assert len(fixtures) == 16
    scenarios = {fixture.metadata["scenario"] for fixture in fixtures}
    assert scenarios == {
        "robot_vacuum",
        "research_assistant",
        "coding_demo",
        "router",
        "workspace_assistant",
    }
    assert all(fixture.tools for fixture in fixtures)


def test_selfbuilt_extra_tools_are_added_to_pool_only():
    fixtures = build_selfbuilt_fixtures(scenario="workspace_assistant")
    fixture = next(item for item in fixtures if item.id == "selfbuilt-sb-multi-005")
    names = {tool.name for tool in fixture.tools}
    assert {"search_notes", "remember"} <= names
    assert len(names) == len(fixture.tools)
    assert fixture.metadata["extra_tools"] == ["remember"]
    assert "remember" not in fixture.metadata["missing_tools"]
    # 前置工具只进工具池，不作为 expected call 的硬断言
    assert all(call["name"] != "remember" for call in fixture.expected["calls"])


def test_selfbuilt_missing_extra_tool_is_not_fabricated(tmp_path, monkeypatch):
    data_dir = tmp_path / "selfbuilt"
    data_dir.mkdir()
    task = {
        "id": "sb-extra-missing",
        "kind": "multi_turn",
        "scenario": "workspace_assistant",
        "turns": ["先记住：我喜欢简洁的回答。", "再根据笔记回答。"],
        "expected_points": [],
        "expected_tools": ["search_notes"],
        "extra_tools": ["ghost_tool"],
        "should_refuse": False,
    }
    (data_dir / "tasks.jsonl").write_text(json.dumps(task, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(fixtures_module, "DATASETS_DIR", tmp_path)

    fixture = build_selfbuilt_fixtures(scenario="workspace_assistant")[0]
    names = {tool.name for tool in fixture.tools}
    assert "search_notes" in names
    assert "ghost_tool" not in names
    assert fixture.metadata["missing_tools"] == ["ghost_tool"]
