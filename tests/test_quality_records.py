# -*- coding: utf-8 -*-
"""运行记录：run / line / metrics 落盘与读取。"""
from core.quality.records import RunStore, Score, Span, read_run


def test_run_store_writes_lines_and_metrics(tmp_path):
    store = RunStore("run-test", root=tmp_path, scenario="demo", trials=2)
    store.record_line(
        case_id="case-1",
        trial=1,
        scenario="demo",
        passed=True,
        scores=[Score("behavior", 1.0, True, "ok")],
        trace_id="trace-1",
        answer="hello",
        tool_names=["search"],
        spans=[Span("s1", "search", kind="tool", latency_ms=12)],
    )
    store.record_line(
        case_id="case-1",
        trial=2,
        scenario="demo",
        passed=False,
        scores=[Score("behavior", 0.0, False, "missing")],
        trace_id="trace-2",
    )
    run = store.finalize(summary={"total": 1})

    assert run["line_count"] == 2
    assert run["case_count"] == 1
    assert run["metrics"]["behavior"]["pass_rate"] == 0.5
    assert run["metrics"]["pass^k"]["value"] == 0.0

    loaded = read_run(store.run_dir)
    assert loaded["run"]["run_id"] == "run-test"
    assert len(loaded["lines"]) == 2
    assert loaded["lines"][0]["trace_id"] == "trace-1"
    assert loaded["lines"][0]["spans"][0]["name"] == "search"
    assert loaded["metrics"]["overall"]["count"] == 2


def test_pass_k_is_one_when_both_trials_pass(tmp_path):
    store = RunStore("run-pass", root=tmp_path, scenario="demo", trials=2)
    for trial in (1, 2):
        store.record_line(
            case_id="case-1",
            trial=trial,
            scenario="demo",
            passed=True,
            scores=[Score("behavior", 1.0, True)],
        )
    run = store.finalize()
    assert run["metrics"]["pass^k"]["value"] == 1.0


def test_finalize_is_repeatable(tmp_path):
    store = RunStore("run-repeat", root=tmp_path)
    store.record_line(case_id="c", trial=1, scenario="demo", passed=True)
    first = store.finalize()
    second = store.finalize()
    assert first["run_id"] == second["run_id"]
    assert second["line_count"] == 1
