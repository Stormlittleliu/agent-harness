# -*- coding: utf-8 -*-
"""统一素材目录：四类资源、URI、词法搜索与 MCP 工具。"""
import json
import os
import subprocess
import sys

import pytest

from core.paths import PROJECT_ROOT
from core.resources.catalog import ResourceCatalog, tokenize
from core.resources.contracts import (
    ResourceDescriptor,
    ResourceKind,
    ResourceNotFoundError,
    ResourceRef,
    ResourceURIError,
    build_uri,
    parse_uri,
)


@pytest.fixture(scope="module")
def catalog():
    # 目录本身是只读的，模块级共享一份即可；不构建任何场景。
    return ResourceCatalog()


def test_catalog_finds_all_four_kinds(catalog):
    items = catalog.list()
    kinds = {item["kind"] for item in items}
    assert {"tool", "workflow", "scenario", "block"} <= kinds

    counts = {item["kind"]: item["count"] for item in catalog.kinds()}
    assert counts["tool"] > 0
    assert counts["workflow"] > 0
    assert counts["scenario"] > 0
    assert counts["block"] > 0


def test_tool_descriptor_has_description_and_args_schema(catalog):
    tool = catalog.get("ah://tool/search_notes")
    assert tool["kind"] == "tool"
    assert tool["name"] == "search_notes"
    assert tool["description"]
    assert tool["input_schema"]["type"] == "object"
    assert "query" in tool["input_schema"]["properties"]
    assert "query" in tool["input_schema"]["required"]
    assert tool["metadata"]["schema_available"] is True


def test_tool_without_schema_gets_empty_object_schema(catalog):
    external = catalog.get("ah://tool/memory_search_nodes")
    assert external["metadata"]["external"] is True
    assert external["input_schema"] == {
        "type": "object",
        "properties": {},
        "required": [],
    }


def test_block_descriptor_exposes_param_schema_and_ports(catalog):
    block = catalog.get("ah://block/retrieve")
    assert block["kind"] == "block"
    assert block["label"] == "检索"
    assert block["description"]
    assert block["input_schema"]["properties"]["tool"]["type"] == "string"
    assert block["input_schema"]["required"] == ["tool"]
    assert block["metadata"]["inputs"][0]["name"] == "input"
    assert any(port["name"] == "tool_result" for port in block["metadata"]["outputs"])


def test_workflow_descriptor_has_nodes_edges_and_input_schema(catalog):
    workflows = catalog.list("workflow")
    assert workflows, "data/specs 下应该至少有 spec 工作流"
    workflow = catalog.get("ah://workflow/flow_demo/qa")
    assert workflow["id"] == "flow_demo/qa"
    assert workflow["metadata"]["node_count"] == len(workflow["metadata"]["nodes"])
    assert any(node["fn"] == "retrieve" for node in workflow["metadata"]["nodes"])
    assert workflow["metadata"]["edges"]
    assert "input" in workflow["input_schema"]["properties"]
    assert workflow["version"] is not None


def test_scenario_descriptor_comes_from_library(catalog):
    scenario = catalog.get("ah://scenario/clothing_service")
    assert scenario["kind"] == "scenario"
    assert scenario["label"] == "服装顾问"
    assert "服装" in scenario["description"]
    assert scenario["metadata"]["from_spec"] is True
    assert scenario["metadata"]["editable"] is True


def test_chinese_search_finds_clothing_and_retrieval(catalog):
    clothing = catalog.search("服装")
    assert any(
        item["kind"] == "scenario" and item["id"] == "clothing_service"
        for item in clothing
    )
    assert any(
        item["kind"] == "tool" and "clothing" in item["id"]
        for item in clothing
    )

    retrieval = catalog.search("检索")
    assert any(item["kind"] == "block" and item["id"] == "retrieve" for item in retrieval)
    assert any(
        item["kind"] == "tool" and item["id"] in {"rag_retrieve", "search_notes", "search_sources"}
        for item in retrieval
    )
    for item in retrieval:
        assert item["score"] > 0
        assert item["match_reasons"]
        assert item["match_reason"]


def test_search_is_stable_and_has_reasons(catalog):
    first = catalog.search("服装 检索", limit=50)
    second = catalog.search("服装 检索", limit=50)
    assert [item["uri"] for item in first] == [item["uri"] for item in second]
    scores = [item["score"] for item in first]
    assert scores == sorted(scores, reverse=True)
    assert all(item["matched_terms"] for item in first)


def test_query_filter_and_limit(catalog):
    filtered = catalog.list("tool", query="笔记")
    assert filtered
    assert all(item["kind"] == "tool" for item in filtered)
    assert len(catalog.list("tool", limit=3)) == 3


def test_uri_construction_and_roundtrip():
    assert build_uri("tool", "search_notes") == "ah://tool/search_notes"
    assert build_uri(ResourceKind.SCENARIO, "flow_demo") == "ah://scenario/flow_demo"
    assert build_uri("workflow", "flow_demo/qa") == "ah://workflow/flow_demo/qa"

    ref = ResourceRef.from_parts("workflow", "flow_demo/qa")
    assert ref.uri == "ah://workflow/flow_demo/qa"
    assert parse_uri(str(ref)) == ref
    assert ResourceRef.from_uri("AH://TOOL/search_notes").kind is ResourceKind.TOOL


@pytest.mark.parametrize(
    "uri",
    [
        "",
        "not-a-uri",
        "http://tool/search_notes",
        "ah://tool/",
        "ah://tool/a/b",
        "ah://tool/search_notes?x=1",
        "ah://tool/search_notes#frag",
        "ah://workflow/flow_demo",
        "ah://workflow//qa",
        "ah://workflow/flow_demo/qa/extra",
        "ah://nope/x",
        "ah://tool/../x",
    ],
)
def test_invalid_uri_raises(uri):
    with pytest.raises(ResourceURIError):
        parse_uri(uri)


def test_get_unknown_resource_raises_not_found(catalog):
    with pytest.raises(ResourceNotFoundError):
        catalog.get("ah://tool/definitely_missing")


def test_invalid_kind_raises(catalog):
    with pytest.raises(ResourceURIError):
        catalog.list("not_a_kind")


def test_descriptor_is_json_serializable(catalog):
    payload = {
        "kinds": catalog.kinds(),
        "all": catalog.list(limit=200),
        "search": catalog.search("工具"),
        "one": catalog.get("ah://tool/search_notes"),
    }
    text = json.dumps(payload, ensure_ascii=False)
    assert "ah://tool/search_notes" in text


def test_jieba_absent_falls_back_to_ngram(monkeypatch):
    import core.resources.catalog as catalog_module

    monkeypatch.setattr(catalog_module, "_JIEBA", None)
    monkeypatch.setattr(catalog_module, "_JIEBA_TRIED", True)
    terms = tokenize("服装检索")
    assert "服装" in terms
    assert "检索" in terms


def test_tool_catalog_does_not_build_scenario_toolboxes(monkeypatch):
    """列目录不能调用 pools.toolbox()（那会构造 RAG/workspace/subagent 等重资源）。"""
    from core.scenarios import pools

    def _boom(*args, **kwargs):
        raise AssertionError("资源目录不应构建场景工具箱")

    monkeypatch.setattr(pools, "toolbox", _boom)
    tools = ResourceCatalog().list("tool")
    assert any(item["id"] == "search_notes" for item in tools)


def test_catalog_builds_without_model_credentials(tmp_path):
    """干净克隆没有 .env 时，资源目录也必须可用且不 import 模型工厂。"""
    env = dict(os.environ)
    for key in list(env):
        if key.endswith("_API_KEY"):
            env.pop(key, None)
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    code = (
        "import sys; "
        "from core.resources.catalog import ResourceCatalog; "
        "c = ResourceCatalog(); c.kinds(); "
        "assert 'core.llm.factory' not in sys.modules, 'resource catalog imported chat model'; "
        "print('ok')"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert "ok" in completed.stdout


def test_mcp_tool_functions_are_directly_callable():
    from core.mcp import resource_server

    listed = json.loads(resource_server.resource_list(kind="tool", limit=5))
    assert listed["ok"] is True
    assert listed["count"] == 5
    assert listed["items"]

    kinds = json.loads(resource_server.resource_kinds())
    assert kinds["ok"] is True
    assert {item["kind"] for item in kinds["kinds"]} == {
        "tool",
        "workflow",
        "scenario",
        "block",
    }

    got = json.loads(resource_server.resource_get("ah://block/retrieve"))
    assert got["ok"] is True
    assert got["resource"]["name"] == "retrieve"

    searched = json.loads(resource_server.resource_search("服装", limit=5))
    assert searched["ok"] is True
    assert any(item["id"] == "clothing_service" for item in searched["items"])

    bad = json.loads(resource_server.resource_get("ah://tool/__missing__"))
    assert bad["ok"] is False
    assert "error" in bad

    invalid = json.loads(resource_server.resource_list(kind="bogus"))
    assert invalid["ok"] is False
    assert "error" in invalid


def test_descriptor_rejects_inconsistent_uri():
    with pytest.raises(ResourceURIError):
        ResourceDescriptor(
            kind=ResourceKind.TOOL,
            id="search_notes",
            uri="ah://tool/other",
        )
