# -*- coding: utf-8 -*-
"""RAG 知识库分类与领域特化 spec 的静态契约。"""
from core.scenarios.pools import tool_names
from core.scenarios.spec import load_active_spec, split_edge, validate_spec
from core.tools.rag.classification import classify


def test_classify_clothing_sources():
    assert classify("服装-尺码推荐.txt").__dict__ == {
        "domain": "clothing",
        "category": "size",
    }
    assert classify("服装-颜色推荐.txt").category == "color"
    assert classify("服装-洗涤养护.txt").category == "care"
    assert classify("服装-新品推荐.md").category == "new"


def test_classify_robot_sources():
    assert classify("故障排除.txt").category == "troubleshoot"
    assert classify("维护保养.txt").category == "maintenance"
    assert classify("选购指南.txt").category == "purchase"
    assert classify("扫地机器人100问.pdf").domain == "robot"


def test_classify_content_fallback():
    assert classify("未知文档.txt", "身高 175，体重 140 斤，选什么尺码").category == "size"
    assert classify("未知文档.txt", "回充失败、连不上 WiFi").category == "troubleshoot"
    assert classify("未知文档.txt", "今天天气不错").domain == "general"


def test_domain_specs_validate_against_their_toolbox():
    for name in ("clothing_service", "retail_router"):
        spec = load_active_spec(name)
        assert spec is not None, name
        available = set(tool_names(name))
        assert set(spec.tools) <= available, (name, spec.tools, available)
        assert validate_spec(spec, tool_names=available) == [], name


def test_clothing_service_has_out_of_scope_branch():
    spec = load_active_spec("clothing_service")
    workflow = spec.workflows["qa"]
    triage = next(node for node in workflow.nodes if node.fn == "branch")
    assert triage.args["miss"] == "out_of_scope"
    assert any(
        split_edge(edge)[2] == "out_of_scope" and split_edge(edge)[1] == "refuse"
        for edge in workflow.edges
    )
