# -*- coding: utf-8 -*-
"""M3：A/B 门槛、采纳写新版本、baseline 保留、一键回退。"""
import json

import pytest

from core.quality.adoption import (
    AdoptionError,
    adopt_candidate,
    evaluate_gate,
    last_adoption,
    rollback_last,
)
from core.scenarios.pattern_to_spec import compile_pattern
from core.scenarios.spec import active_spec_path, save_spec
from core.scenarios.spec_nodes import NODE_REGISTRY


def _pattern(steps=("retrieve", "llm_answer", "require_citation")):
    return {
        "pattern_id": "pat-adopt-1",
        "name": " → ".join(steps),
        "kind": "sequence",
        "scope": {"scenario": "demo"},
        "steps": list(steps),
        "support": 5,
        "success_rate": 1.0,
        "lift": 0.2,
        "evidence": ["run-a:1"],
    }


def _shadow(**overrides):
    shadow = {
        "shadow_id": "shadow-1",
        "baseline": {
            "pass_k": 0.8,
            "pass_rate": 0.8,
            "outcome_rate": 0.9,
            "avg_tokens": 100.0,
            "avg_latency_ms": 1000.0,
        },
        "candidate": {
            "pass_k": 0.9,
            "pass_rate": 0.9,
            "outcome_rate": 0.9,
            "avg_tokens": 110.0,
            "avg_latency_ms": 1100.0,
        },
        "comparison": {"safety_regressions": []},
    }
    for section, values in overrides.items():
        shadow[section].update(values)
    return shadow


@pytest.fixture()
def workspace(tmp_path):
    """一个真实的 v1 active + 一个候选文件。"""
    root = tmp_path / "specs"
    pattern = _pattern()
    base = compile_pattern(pattern, tool_names={"search_notes"}, root=root, write=False).spec
    save_spec(base, root=root)
    candidate = compile_pattern(pattern, tool_names={"search_notes"}, root=root)
    return root, candidate.path


def test_gate_passes_when_nothing_regresses():
    gate = evaluate_gate(_shadow())
    assert gate.passed
    assert gate.to_dict()["metrics"]["baseline_pass_k"] == 0.8


def test_gate_rejects_pass_k_drop():
    gate = evaluate_gate(_shadow(candidate={"pass_k": 0.7, "pass_rate": 0.7}))
    assert not gate.passed
    assert any("pass^k" in reason for reason in gate.reasons)


def test_gate_rejects_outcome_drop():
    gate = evaluate_gate(_shadow(candidate={"outcome_rate": 0.8}))
    assert not gate.passed
    assert any("outcome" in reason for reason in gate.reasons)


def test_gate_rejects_cost_and_latency_over_budget():
    gate = evaluate_gate(_shadow(candidate={"avg_tokens": 500.0, "avg_latency_ms": 9000.0}))
    assert not gate.passed
    assert any("成本" in reason for reason in gate.reasons)
    assert any("延迟" in reason for reason in gate.reasons)


def test_gate_rejects_safety_regression():
    gate = evaluate_gate(_shadow(comparison={"safety_regressions": ["case-danger"]}))
    assert not gate.passed
    assert any("安全" in reason for reason in gate.reasons)


def test_adopt_writes_new_version_and_keeps_baseline(workspace):
    root, candidate_path = workspace
    gate = evaluate_gate(_shadow())
    record = adopt_candidate(
        "demo",
        candidate_path,
        gate,
        shadow_id="shadow-1",
        root=root,
        out_root=root.parent / "adoptions",
    )

    assert record["baseline_version"] == "v1"
    assert record["adopted_version"] == "v2"
    active = active_spec_path("demo", root)
    assert active is not None and active.name == "v2.json"
    assert (root / "demo" / "v1.json").is_file()
    payload = json.loads(active.read_text(encoding="utf-8"))
    assert payload["provenance"]["status"] == "adopted"
    assert payload["provenance"]["pattern_id"] == "pat-adopt-1"
    assert payload["provenance"]["baseline_version"] == "v1"

    adoption = last_adoption("demo", out_root=root.parent / "adoptions")
    assert adoption is not None and adoption["adoption_id"] == record["adoption_id"]


def test_adopt_refuses_failed_gate_and_leaves_active_untouched(workspace):
    root, candidate_path = workspace
    before = active_spec_path("demo", root).read_text(encoding="utf-8")
    gate = evaluate_gate(_shadow(candidate={"pass_k": 0.1, "pass_rate": 0.1}))
    with pytest.raises(AdoptionError):
        adopt_candidate("demo", candidate_path, gate, root=root)
    assert active_spec_path("demo", root).read_text(encoding="utf-8") == before
    assert not (root / "demo" / "v2.json").exists()


def test_rollback_restores_baseline_without_deleting_new_version(workspace):
    root, candidate_path = workspace
    adopt_candidate(
        "demo",
        candidate_path,
        evaluate_gate(_shadow()),
        root=root,
        out_root=root.parent / "adoptions",
    )
    record = rollback_last("demo", root=root, out_root=root.parent / "adoptions")

    assert record["restored_version"] == "v1"
    active = active_spec_path("demo", root)
    assert active is not None and active.name == "v1.json"
    assert (root / "demo" / "v2.json").is_file()
    assert (root.parent / "adoptions" / "demo" / f"{record['adoption_id']}.json").is_file()


def test_adopt_requires_active_baseline(tmp_path):
    candidate = compile_pattern(
        _pattern(), tool_names={"search_notes"}, root=tmp_path
    )
    with pytest.raises(AdoptionError) as excinfo:
        adopt_candidate("demo", candidate.path, evaluate_gate(_shadow()), root=tmp_path)
    assert any("baseline" in error for error in excinfo.value.errors)


def test_candidate_must_match_scenario(workspace, tmp_path):
    root, candidate_path = workspace
    payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    payload["name"] = "other"
    other = tmp_path / "other.json"
    other.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(AdoptionError):
        adopt_candidate("demo", other, evaluate_gate(_shadow()), root=root)


def test_every_block_still_registered():
    assert "retrieve" in NODE_REGISTRY
