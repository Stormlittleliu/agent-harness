# -*- coding: utf-8 -*-
from core.agent.contracts import Scenario
from core.agent.framework import FrameworkAgent
from core.quality.structured_eval import evaluate_case, extract_report, summarize_results
from core.scenarios.registry import get_scenario
from core.scenarios.structured_demo.schema import ReportSchema


def _report(**overrides):
    data = {
        "summary": "接口联调延后到周五，测试环境不稳定是主要风险。",
        "evidence": ["接口联调延后到周五", "测试环境本周不稳定"],
        "confidence": 0.8,
        "next_actions": ["先保证登录链路"],
        "risks": ["测试环境可能影响回归"],
    }
    data.update(overrides)
    return ReportSchema(**data)


class _FakeAgent:
    last_trace_id = "trace-structured"

    def __init__(self, response):
        self.response = response

    def invoke(self, query):
        return {"messages": [], "structured_response": self.response}


def test_extract_report_accepts_schema_and_rejects_incomplete_dict():
    report, error = extract_report({"structured_response": _report()})
    assert report is not None and error is None

    report, error = extract_report({"structured_response": {"summary": "只有摘要"}})
    assert report is None
    assert "evidence" in error or "Field required" in error


def test_evaluate_case_passes_with_schema_and_points():
    case = {
        "id": "structured-test-001",
        "category": "office",
        "question": "q",
        "expected_points": ["周五", "测试环境"],
        "min_evidence": 2,
        "min_confidence": 0.5,
    }
    result = evaluate_case(_FakeAgent(_report()), case)
    assert result["schema_ok"] is True
    assert result["coverage"] == 1.0
    assert result["passed"] is True
    assert result["trace_id"] == "trace-structured"


def test_evaluate_case_fails_when_evidence_too_short():
    case = {
        "id": "structured-test-002",
        "category": "office",
        "question": "q",
        "expected_points": ["周五"],
        "min_evidence": 3,
        "min_confidence": 0.5,
    }
    result = evaluate_case(_FakeAgent(_report()), case)
    assert result["schema_ok"] is True
    assert result["evidence_ok"] is False
    assert result["passed"] is False


def test_summarize_results():
    case = {"id": "a", "category": "office", "question": "q", "expected_points": ["周五"]}
    result = evaluate_case(_FakeAgent(_report()), case)
    summary = summarize_results("structured_demo", [result])
    assert summary["total"] == 1
    assert summary["passed"] == 1
    assert summary["schema_ok"] == 1
    assert summary["avg_evidence"] == 2.0


def test_framework_passes_response_format_to_create_agent(monkeypatch):
    captured = {}

    def fake_create_agent(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr("core.agent.framework.create_agent", fake_create_agent)
    scenario = Scenario(
        name="test",
        description="test",
        model=object(),
        system_prompt="test",
        tools=[],
        enable_todo=False,
        enable_summarization=False,
        checkpoint=False,
        response_format=ReportSchema,
    )
    FrameworkAgent(scenario)
    assert captured["response_format"] is ReportSchema


def test_structured_scenario_registers_response_format():
    scenario = get_scenario("structured_demo")
    assert scenario.response_format is ReportSchema
    assert scenario.cases_path is not None
    assert scenario.cases_path.exists()
