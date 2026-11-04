# -*- coding: utf-8 -*-
"""M2：线性范式 → candidate spec，不覆盖 active，必须能编译。"""
import json

import pytest

from core.scenarios.pattern_to_spec import (
    PatternCompileError,
    compile_pattern,
    pattern_to_spec,
    save_candidate,
)
from core.scenarios.spec import END, START, ScenarioSpec, build_workflows


def _source_spec() -> ScenarioSpec:
    return ScenarioSpec.model_validate({
        "schema_version": 1,
        "name": "demo",
        "description": "演示场景",
        "tools": ["search_notes"],
        "workflows": {
            "qa": {
                "nodes": [
                    {
                        "id": "lookup",
                        "fn": "call_tool",
                        "args": {
                            "tool": "search_notes",
                            "args": '{"query": "{input}"}',
                            "save_to": "tool_result",
                        },
                    },
                    {
                        "id": "answer",
                        "fn": "llm_text",
                        "args": {"prompt": "根据 {tool_result} 回答", "save_to": "answer"},
                    },
                    {"id": "cite", "fn": "require_citation", "args": {}},
                ],
                "edges": [
                    [START, "lookup"],
                    ["lookup", "answer"],
                    ["answer", "cite"],
                    ["cite", END],
                ],
            }
        },
    })


def _pattern(steps, pattern_id="pat-test", scenario="demo"):
    return {
        "pattern_id": pattern_id,
        "name": " → ".join(steps),
        "kind": "sequence",
        "scope": {"scenario": scenario, "intent": "qa"},
        "steps": list(steps),
        "support": 3,
        "success_rate": 1.0,
        "lift": 0.25,
        "evidence": ["run-a:1", "run-b:2"],
    }


def test_linear_pattern_compiles_to_valid_spec(tmp_path):
    spec = pattern_to_spec(
        _pattern(["retrieve", "llm_answer", "require_citation"]),
        tool_names={"search_notes"},
    )
    assert spec.name == "demo"
    workflow = spec.workflows["mined"]
    assert [node.fn for node in workflow.nodes] == [
        "retrieve",
        "llm_answer",
        "require_citation",
    ]
    assert workflow.edges[0] == [START, workflow.nodes[0].id]
    assert workflow.edges[-1] == [workflow.nodes[-1].id, END]
    assert spec.provenance["source"] == "mined"
    assert spec.provenance["pattern_id"] == "pat-test"
    assert spec.provenance["evidence_runs"] == ["run-a", "run-b"]

    stub = type("S", (), {"tools": [type("T", (), {"name": "search_notes"})()]})()
    assert "mined" in build_workflows(spec, stub)


def test_tool_and_model_tokens_map_to_blocks():
    spec = pattern_to_spec(
        _pattern(["tool:search_notes", "model"]),
        tool_names={"search_notes"},
    )
    nodes = spec.workflows["mined"].nodes
    assert [node.fn for node in nodes] == ["call_tool", "llm_answer"]
    assert nodes[0].args["tool"] == "search_notes"
    assert nodes[0].args["save_to"] == "tool_result"


def test_source_spec_nodes_keep_their_args():
    source = _source_spec()
    spec = pattern_to_spec(
        _pattern(["lookup", "answer", "cite"]),
        source_spec=source,
        tool_names={"search_notes"},
    )
    nodes = spec.workflows["mined"].nodes
    assert [node.fn for node in nodes] == ["call_tool", "llm_text", "require_citation"]
    assert nodes[0].args["save_to"] == "tool_result"
    assert "tool_result" in nodes[1].args["prompt"]


def test_branch_pattern_is_rejected():
    with pytest.raises(PatternCompileError) as excinfo:
        pattern_to_spec(_pattern(["branch", "llm_answer"]), tool_names={"search_notes"})
    assert any("线性" in error for error in excinfo.value.errors)


def test_unknown_step_is_rejected():
    with pytest.raises(PatternCompileError) as excinfo:
        pattern_to_spec(_pattern(["ghost_step"]), tool_names={"search_notes"})
    assert any("ghost_step" in error for error in excinfo.value.errors)


def test_required_tool_missing_is_rejected():
    with pytest.raises(PatternCompileError) as excinfo:
        pattern_to_spec(_pattern(["retrieve", "llm_answer"]), tool_names=set())
    assert any("需要工具" in error for error in excinfo.value.errors)


def test_compile_writes_candidate_without_touching_active(tmp_path):
    root = tmp_path / "specs"
    scenario_dir = root / "demo"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "v1.json").write_text("{}", encoding="utf-8")
    (scenario_dir / "active.json").write_text(
        json.dumps({"version": 1, "file": "v1.json"}), encoding="utf-8"
    )

    candidate = compile_pattern(
        _pattern(["retrieve", "llm_answer", "require_citation"]),
        tool_names={"search_notes"},
        root=root,
    )
    assert candidate.path is not None
    assert candidate.path.parent.name == "candidates"
    assert candidate.path.name == "pat-test.json"
    assert (scenario_dir / "active.json").read_text(encoding="utf-8") == json.dumps(
        {"version": 1, "file": "v1.json"}
    )
    assert not (scenario_dir / "v2.json").exists()

    payload = json.loads(candidate.path.read_text(encoding="utf-8"))
    assert payload["name"] == "demo"
    assert payload["provenance"]["pattern_id"] == "pat-test"
    assert [node["fn"] for node in payload["workflows"]["mined"]["nodes"]] == [
        "retrieve",
        "llm_answer",
        "require_citation",
    ]


def test_dry_run_does_not_write(tmp_path):
    candidate = compile_pattern(
        _pattern(["retrieve", "llm_answer"]),
        tool_names={"search_notes"},
        root=tmp_path,
        write=False,
    )
    assert candidate.path is None
    assert not (tmp_path / "demo").exists()


def test_save_candidate_sanitizes_pattern_id(tmp_path):
    spec = pattern_to_spec(
        _pattern(["retrieve", "llm_answer"]),
        tool_names={"search_notes"},
    )
    path = save_candidate(spec, "pat/../../evil", root=tmp_path)
    assert path.parent.name == "candidates"
    assert ".." not in path.name


def test_cli_compiles_pattern_to_temp_root(tmp_path):
    from core.scenarios.pattern_to_spec import main

    payload = {"patterns": [_pattern(["retrieve", "llm_answer", "require_citation"])]}
    patterns_path = tmp_path / "patterns.json"
    patterns_path.write_text(json.dumps(payload), encoding="utf-8")

    code = main([
        "--patterns", str(patterns_path),
        "--tools", "search_notes",
        "--scenario", "demo",
        "--root", str(tmp_path / "specs"),
    ])
    assert code == 0
    assert (tmp_path / "specs" / "demo" / "candidates" / "pat-test.json").is_file()


def test_every_active_spec_still_has_no_port_errors():
    from pathlib import Path

    from core.scenarios.spec import load_active_spec, validate_spec

    for directory in sorted(Path("data/specs").iterdir()):
        if not (directory / "active.json").is_file():
            continue
        spec = load_active_spec(directory.name)
        assert spec is not None
        assert validate_spec(spec) == [], directory.name
