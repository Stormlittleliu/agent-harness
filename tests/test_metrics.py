# -*- coding: utf-8 -*-
from core.quality.metrics import score_case


def test_expected_tools_any_accepts_alternative():
    case = {
        "question": "recall",
        "expected_points": ["小户型"],
        "expected_tools": [],
        "expected_tools_any": ["memory_read_graph", "memory_search_nodes"],
        "should_refuse": False,
    }
    result = score_case(case, "你喜欢小户型", ["memory_search_nodes"])
    assert result["tools_ok"] is True
    assert result["passed"] is True


def test_refusal_case_passes_on_marker():
    case = {
        "question": "today weather",
        "expected_points": [],
        "should_refuse": True,
    }
    assert score_case(case, "没有相关信息，无法回答", [])["passed"] is True
