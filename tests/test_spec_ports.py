# -*- coding: utf-8 -*-
"""块端口契约：类型兼容、参数驱动的动态端口、边上的数据流校验。"""
from pathlib import Path

from core.scenarios.spec import NodeSpec, load_active_spec, validate_port_flow, validate_spec
from core.scenarios.spec_nodes import (
    NODE_INPUTS,
    NODE_OUTPUTS,
    NODE_REGISTRY,
    PortSpec,
    ResolvedPorts,
    block_ports,
    types_compatible,
)


# ---------------------------------------------------------------- 类型兼容


def test_types_compatible_identity_and_aliases():
    assert types_compatible("text", "text")
    assert types_compatible("str", "text")
    assert types_compatible("int", "number")
    assert types_compatible("float", "number")
    assert types_compatible("bool", "boolean")
    assert types_compatible("dict", "json")


def test_any_is_compatible_in_both_directions():
    assert types_compatible("any", "text")
    assert types_compatible("text", "any")
    assert types_compatible("*", "json")


def test_different_types_are_not_compatible():
    assert not types_compatible("text", "number")
    assert not types_compatible("json", "text")
    assert not types_compatible("boolean", "text")
    assert not types_compatible("nonsense", "text")


# ---------------------------------------------------------------- 端口解析


def test_every_block_registers_ports():
    assert set(NODE_INPUTS) == set(NODE_REGISTRY)
    assert set(NODE_OUTPUTS) == set(NODE_REGISTRY)
    for fn in NODE_REGISTRY:
        ports = block_ports(fn, {})
        assert ports.inputs or ports.outputs, f"{fn} 没有任何端口"


def test_call_tool_save_target_becomes_output_port():
    ports = block_ports(
        "call_tool",
        {"save_to": "scratch.records", "args": '{"query": "{input}"}'},
    )
    output_names = [port.name for port in ports.outputs]
    assert "scratch.records" in output_names
    assert "answer" not in output_names  # 默认槽位被 save_to 覆盖
    assert "tool_result" in output_names  # 工具带 docs 时还会写材料
    assert [port.name for port in ports.inputs] == ["input"]


def test_fan_out_reads_queries_from_and_writes_save_to():
    ports = block_ports(
        "fan_out",
        {"queries_from": "scratch.subquestions", "save_to": "scratch.notes"},
    )
    input_port = next(port for port in ports.inputs if port.name == "scratch.subquestions")
    assert input_port.required
    assert "scratch.notes" in [port.name for port in ports.outputs]


def test_llm_text_collects_template_placeholders():
    ports = block_ports(
        "llm_text",
        {"prompt": "根据 {scratch.findings} 回答 {input}；{missing} 不算", "save_to": "answer"},
    )
    names = [port.name for port in ports.inputs]
    assert names == ["scratch.findings", "input"]
    assert all(not port.required for port in ports.inputs)  # 占位符缺失会渲染成空串
    assert [port.name for port in ports.outputs] == ["answer"]


def test_retrieve_query_key_changes_input_port():
    ports = block_ports("retrieve", {"query_key": "scratch.question"})
    assert [port.name for port in ports.inputs] == ["scratch.question"]
    assert "input" not in [port.name for port in ports.inputs]


# ---------------------------------------------------------------- 数据流校验


def test_missing_required_input_is_reported():
    nodes = [NodeSpec(id="cite", fn="require_citation")]
    edges = [["__start__", "cite"], ["cite", "__end__"]]
    errors = validate_port_flow("workflow[qa]", nodes, edges)
    assert any("cite" in error and "缺少输入 answer" in error for error in errors)


def test_upstream_output_satisfies_downstream_input():
    nodes = [
        NodeSpec(id="retrieve", fn="retrieve", args={"tool": "search_notes"}),
        NodeSpec(id="answer", fn="llm_answer"),
        NodeSpec(id="cite", fn="require_citation"),
    ]
    edges = [
        ["__start__", "retrieve"],
        ["retrieve", "answer"],
        ["answer", "cite"],
        ["cite", "__end__"],
    ]
    assert validate_port_flow("workflow[qa]", nodes, edges) == []


def test_type_mismatch_between_nodes_is_reported():
    def resolve(fn: str, args: dict) -> ResolvedPorts:
        if fn == "source":
            return ResolvedPorts(outputs=(PortSpec("answer", "number", required=True),))
        return ResolvedPorts(inputs=(PortSpec("answer", "text", required=True),))

    nodes = [NodeSpec(id="src", fn="source"), NodeSpec(id="dst", fn="dst")]
    edges = [["__start__", "src"], ["src", "dst"], ["dst", "__end__"]]
    errors = validate_port_flow("workflow[qa]", nodes, edges, resolve=resolve)
    assert any("输入 answer 需要 text" in error and "number" in error for error in errors)


def test_optional_input_missing_is_not_an_error():
    def resolve(fn: str, args: dict) -> ResolvedPorts:
        return ResolvedPorts(inputs=(PortSpec("scratch.optional", "text", required=False),))

    nodes = [NodeSpec(id="only", fn="only")]
    edges = [["__start__", "only"], ["only", "__end__"]]
    assert validate_port_flow("workflow[qa]", nodes, edges, resolve=resolve) == []


# ---------------------------------------------------------------- 真实 spec


def test_active_specs_pass_port_validation():
    root = Path("data/specs")
    checked = 0
    for directory in sorted(root.iterdir()):
        if not (directory / "active.json").is_file():
            continue
        spec = load_active_spec(directory.name)
        assert spec is not None
        errors = validate_spec(spec)
        assert errors == [], f"{directory.name}: {errors}"
        checked += 1
    assert checked >= 9
