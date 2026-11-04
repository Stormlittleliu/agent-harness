# -*- coding: utf-8 -*-
"""轨迹挖掘 M1：序列/转移范式、门槛、证据与落盘。"""
import json

from core.quality.mining import (
    MinedLine,
    load_mined_lines,
    mine_and_write,
    mine_patterns,
    node_sequence,
)
from core.quality.records import RunStore, Span


def _spans(nodes, *, tokens=100, latency=10):
    return [
        Span(
            span_id=f"span-{index}",
            name=node,
            kind="node",
            status="ok",
            tokens=tokens,
            latency_ms=latency,
            metadata={"node": node},
        )
        for index, node in enumerate(nodes)
    ]


def _write_run(root, run_id="run-a", scenario="demo", rows=None, status="completed"):
    store = RunStore(run_id, root=root, scenario=scenario, trials=1)
    for case_id, passed, nodes in rows or []:
        store.record_line(
            case_id=case_id,
            trial=1,
            scenario=scenario,
            passed=passed,
            spans=_spans(nodes),
        )
    store.finalize(status=status)
    return store


def _rows():
    return [
        ("case-1", True, ["search", "answer", "cite"]),
        ("case-2", True, ["search", "answer", "cite"]),
        ("case-3", True, ["search", "answer", "cite"]),
        ("case-4", False, ["search", "answer", "rewrite"]),
    ]


# ---------------------------------------------------------------- 序列归一化


def test_node_sequence_prefers_metadata_node_and_collapses_duplicates():
    spans = [
        {"kind": "tool", "name": "search_notes", "metadata": {"node": "search"}},
        {"kind": "tool", "name": "search_notes", "metadata": {"node": "search"}},
        {"kind": "model", "name": "deepseek", "metadata": {"node": "answer"}},
        {"kind": "node", "name": "verify"},
    ]
    assert node_sequence(spans) == ["search", "answer", "verify"]


def test_node_sequence_falls_back_to_explicit_transitions():
    spans = [{"kind": "branch", "from_node": "verify", "to_node": "rewrite"}]
    assert node_sequence(spans) == ["verify", "rewrite"]


def test_generic_react_node_uses_tool_name():
    spans = [
        {"kind": "model", "name": "deepseek", "metadata": {"node": "model"}},
        {"kind": "tool", "name": "search_notes", "metadata": {"node": "tools"}},
    ]
    assert node_sequence(spans) == ["model", "tool:search_notes"]


# ---------------------------------------------------------------- 挖掘结果


def test_sequence_pattern_keeps_success_and_reports_evidence(tmp_path):
    _write_run(tmp_path / "runs", rows=_rows())
    result = mine_and_write(
        runs_root=tmp_path / "runs",
        out_root=tmp_path / "patterns",
        min_support=2,
        max_len=4,
        top_k=10,
        mining_id="mine-test",
    )

    assert result["line_count"] == 4
    patterns = result["patterns"]
    names = [pattern["name"] for pattern in patterns]
    assert "search → answer → cite" in names
    # search → answer 的成功率和基线一样（失败用例也走过），lift=0，不该当范式。
    assert "search → answer" not in names

    pattern = next(item for item in patterns if item["name"] == "search → answer → cite")
    assert pattern["kind"] == "sequence"
    assert pattern["support"] == 3
    assert pattern["total"] == 3
    assert pattern["success_rate"] == 1.0
    assert pattern["lift"] == 0.25
    assert pattern["status"] == "candidate"
    assert pattern["source"] == "mined"
    assert len(pattern["evidence"]) == 3
    assert pattern["cost"]["avg_tokens"] == 300  # 3 个节点 × 100

    out_dir = tmp_path / "patterns" / "mine-test"
    assert (out_dir / "patterns.json").is_file()
    assert (out_dir / "patterns.md").is_file()
    payload = json.loads((out_dir / "patterns.json").read_text(encoding="utf-8"))
    assert payload["mining_version"] == 1
    assert payload["params"]["min_support"] == 2
    assert any(item["name"] == "search → answer → cite" for item in payload["patterns"])


def test_transition_pattern_is_kept_when_sequence_is_not():
    patterns = mine_patterns(
        [MinedLine("r1", "run", "demo", True, ["search", "answer", "cite"])]
        + [
            MinedLine("r2", "run", "demo", True, ["search", "answer", "cite"]),
            MinedLine("r3", "run", "demo", False, ["search", "answer", "rewrite"]),
        ],
        min_support=2,
    )
    names = [pattern.name for pattern in patterns]
    assert "answer → cite" in names
    transition = next(pattern for pattern in patterns if pattern.name == "answer → cite")
    assert transition.kind == "transition"
    assert transition.transitions == [["answer", "cite"]]
    assert patterns[0].score >= patterns[-1].score


def test_min_support_threshold_filters_everything(tmp_path):
    _write_run(tmp_path / "runs", rows=_rows())
    result = mine_and_write(
        runs_root=tmp_path / "runs",
        out_root=tmp_path / "patterns",
        min_support=4,
        mining_id="mine-empty",
    )
    assert result["patterns"] == []
    markdown = (tmp_path / "patterns" / "mine-empty" / "patterns.md").read_text(encoding="utf-8")
    assert "没有达到门槛" in markdown


def test_perfect_baseline_explains_why_there_is_no_pattern(tmp_path):
    _write_run(
        tmp_path / "runs",
        rows=[("case-1", True, ["search", "answer", "cite"]) for _ in range(3)],
    )
    result = mine_and_write(
        runs_root=tmp_path / "runs",
        out_root=tmp_path / "patterns",
        min_support=2,
        mining_id="mine-perfect",
    )
    assert result["patterns"] == []
    markdown = (tmp_path / "patterns" / "mine-perfect" / "patterns.md").read_text(encoding="utf-8")
    assert "基线已经是 100%" in markdown


def test_failed_run_is_ignored(tmp_path):
    _write_run(tmp_path / "runs", run_id="run-failed", rows=_rows(), status="failed")
    lines, run_ids = load_mined_lines(tmp_path / "runs")
    assert lines == []
    assert run_ids == []


def test_scenario_filter_and_bucketing(tmp_path):
    _write_run(tmp_path / "runs", run_id="run-a", scenario="demo", rows=_rows())
    _write_run(
        tmp_path / "runs",
        run_id="run-b",
        scenario="other",
        rows=[
            ("case-x", True, ["plan", "act", "check"]),
            ("case-y", True, ["plan", "act", "check"]),
            ("case-z", True, ["plan", "act", "check"]),
            ("case-w", False, ["plan", "act", "stop"]),
        ],
    )
    lines, run_ids = load_mined_lines(tmp_path / "runs", scenario="other")
    assert run_ids == ["run-b"]
    assert {line.scenario for line in lines} == {"other"}

    result = mine_and_write(
        runs_root=tmp_path / "runs",
        out_root=tmp_path / "patterns",
        min_support=2,
        mining_id="mine-all",
    )
    assert set(result["baseline"]) == {"demo", "other"}
    assert {item["scope"]["scenario"] for item in result["patterns"]} == {"demo", "other"}


def test_intent_buckets_do_not_mix():
    lines = [
        MinedLine("qa-1", "run", "demo", True, ["search", "answer", "cite"], intent="qa"),
        MinedLine("qa-2", "run", "demo", True, ["search", "answer", "cite"], intent="qa"),
        MinedLine("qa-3", "run", "demo", False, ["search", "answer", "rewrite"], intent="qa"),
        MinedLine("note-1", "run", "demo", True, ["plan", "write", "save"], intent="note"),
        MinedLine("note-2", "run", "demo", False, ["plan", "write", "drop"], intent="note"),
    ]
    patterns = mine_patterns(lines, min_support=2)
    assert patterns
    assert {pattern.scope.get("intent") for pattern in patterns} == {"qa"}
    assert all(pattern.scope.get("scenario") == "demo" for pattern in patterns)


def test_empty_or_missing_runs_root_is_safe(tmp_path):
    result = mine_and_write(
        runs_root=tmp_path / "missing",
        out_root=tmp_path / "patterns",
        mining_id="mine-none",
    )
    assert result["patterns"] == []
    assert result["line_count"] == 0
    assert (tmp_path / "patterns" / "mine-none" / "patterns.json").is_file()
