# -*- coding: utf-8 -*-
"""对象索引单测：不加载模型 / Chroma，只验证案例到实现对象的映射。"""
from types import SimpleNamespace

from core.agent.contracts import Scenario
from core.agent.middleware.generic import LimitStepsMiddleware
from core.interfaces.dashboard.objects import (
    build_object_index,
    case_object_chain,
    case_tool_index,
    ref_from_object,
)
from core.tools.business.tools import get_weather


def _agent() -> SimpleNamespace:
    scenario = Scenario(
        name="unit_test",
        description="对象索引测试场景",
        model=object(),
        system_prompt="",
        tools=[get_weather],
        middleware=[],
    )
    return SimpleNamespace(
        scenario=scenario,
        middleware=[LimitStepsMiddleware(3)],
    )


def test_object_index_resolves_tool_and_middleware_source():
    index = build_object_index(_agent())

    tool = index.tools["get_weather"]
    assert tool.file == "core/tools/business/tools.py"
    assert tool.lineno and tool.lineno > 0
    assert tool.source and "def get_weather" in tool.source

    middleware = index.find("middleware", "LimitStepsMiddleware")
    assert middleware is not None
    assert middleware.file == "core/agent/middleware/generic.py"
    assert middleware.lineno and middleware.lineno > 0

    assert index.eval_refs["evaluate_case"].file == "core/quality/agent_eval.py"
    assert index.eval_refs["score_case"].file == "core/quality/metrics.py"


def test_case_tool_index_maps_expected_and_actual_usage():
    usage = case_tool_index(
        [
            {"id": "case-a", "expected_tools": ["get_weather"]},
            {"id": "case-b", "expected_tools": ["get_weather"]},
        ],
        [
            {"id": "case-a", "tool_names": ["get_weather"], "passed": True},
        ],
    )
    assert usage["get_weather"]["expected"] == ["case-a", "case-b"]
    assert usage["get_weather"]["actual"] == ["case-a"]
    assert usage["get_weather"]["passed"] == ["case-a"]


def test_case_object_chain_contains_concrete_objects():
    agent = _agent()
    index = build_object_index(agent)
    chain = case_object_chain(
        agent,
        {
            "id": "case-a",
            "expected_tools": ["get_weather"],
            "tool_names": ["get_weather"],
            "trace_id": "run-test",
            "passed": True,
        },
        index=index,
    )
    kinds = {ref.kind for ref in chain}
    assert {"scenario", "tool", "middleware", "eval", "trace"} <= kinds
    trace = next(ref for ref in chain if ref.kind == "trace")
    assert trace.name == "run-test"


def test_missing_object_degrades_without_raising():
    ref = ref_from_object("tool", "missing", None)
    assert ref.external is True
    assert ref.note
    assert ref.location
