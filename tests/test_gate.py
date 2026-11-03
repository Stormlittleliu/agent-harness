# -*- coding: utf-8 -*-
import json
from pathlib import Path

from core.quality.gate import check_selfbuilt, evaluate


def _write(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_gate_passes_with_all_reports(tmp_path: Path):
    bfcl = _write(tmp_path / "bfcl.json", {
        "summary": {"simple_exact_acc": 0.95, "irrelevance_no_call_rate": 0.90}
    })
    public = _write(tmp_path / "public.json", {
        "summary": {"MultiHop-RAG": {"hit_at_4": 0.60}}
    })
    agent = _write(tmp_path / "agent.json", {
        "summary": {"total": 5, "passed": 5}
    })
    structured = _write(tmp_path / "structured.json", {
        "summary": {"total": 5, "passed": 5, "schema_ok": 5}
    })

    result = evaluate(bfcl, public, agent, structured)
    assert result["ok"] is True
    assert all(item["ok"] for item in result["checks"])


def test_gate_fails_on_regression(tmp_path: Path):
    bfcl = _write(tmp_path / "bfcl.json", {
        "summary": {"simple_exact_acc": 0.80, "irrelevance_no_call_rate": 0.90}
    })
    public = _write(tmp_path / "public.json", {
        "summary": {"MultiHop-RAG": {"hit_at_4": 0.60}}
    })
    agent = _write(tmp_path / "agent.json", {
        "summary": {"total": 5, "passed": 4}
    })
    structured = _write(tmp_path / "structured.json", {
        "summary": {"total": 5, "passed": 5, "schema_ok": 4}
    })

    result = evaluate(bfcl, public, agent, structured)
    assert result["ok"] is False
    failed = {item["name"] for item in result["checks"] if not item["ok"]}
    assert "BFCL exact" in failed
    assert "coding_demo pass" in failed
    assert "structured schema" in failed


def test_gate_marks_missing_report(tmp_path: Path):
    missing = tmp_path / "missing.json"
    bfcl = _write(tmp_path / "bfcl.json", {
        "summary": {"simple_exact_acc": 0.95, "irrelevance_no_call_rate": 0.90}
    })
    result = evaluate(bfcl, missing, missing, missing)
    assert result["ok"] is False
    assert any(item["status"] == "missing" for item in result["checks"])


def test_selfbuilt_check_pass_and_fail(tmp_path: Path):
    good = _write(tmp_path / "good.json", {"summary": {"total": 10, "passed": 8}})
    bad = _write(tmp_path / "bad.json", {"summary": {"total": 10, "passed": 3}})
    thresholds = {"selfbuilt_pass": 0.6}

    assert check_selfbuilt(good, thresholds)[0]["ok"] is True
    assert check_selfbuilt(bad, thresholds)[0]["ok"] is False


def test_selfbuilt_missing_report(tmp_path: Path):
    checks = check_selfbuilt(tmp_path / "none.json", {"selfbuilt_pass": 0.6})
    assert checks[0]["status"] == "missing"
    assert checks[0]["ok"] is False


def test_evaluate_includes_selfbuilt_when_given(tmp_path: Path):
    bfcl = _write(tmp_path / "bfcl.json", {
        "summary": {"simple_exact_acc": 0.95, "irrelevance_no_call_rate": 0.90}
    })
    public = _write(tmp_path / "public.json", {
        "summary": {"MultiHop-RAG": {"hit_at_4": 0.60}}
    })
    agent = _write(tmp_path / "agent.json", {"summary": {"total": 5, "passed": 5}})
    structured = _write(tmp_path / "structured.json", {
        "summary": {"total": 5, "passed": 5, "schema_ok": 5}
    })
    selfbuilt = _write(tmp_path / "selfbuilt.json", {"summary": {"total": 10, "passed": 9}})

    result = evaluate(bfcl, public, agent, structured, selfbuilt_path=selfbuilt)
    names = {item["name"] for item in result["checks"]}
    assert "selfbuilt pass" in names
    assert result["ok"] is True
