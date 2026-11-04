# -*- coding: utf-8 -*-
"""场景编辑器的纯逻辑：草稿 -> spec -> 编译 -> 存版本，以及通用 spec 场景。

全部在 tmp_path 上跑，不碰真实 data/specs（flow_demo 除外）。
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.scenarios import spec_edit
from core.scenarios.generic import build_generic_spec_scenario, spec_scenario_names, spec_tool_names
from core.scenarios.ownership import eject
from core.scenarios.registry import get_scenario, list_scenarios
from core.scenarios.spec import SpecError, build_workflows, save_spec

TOOLS = set(spec_tool_names())


def _stub(draft: dict) -> SimpleNamespace:
    return SimpleNamespace(
        tools=[SimpleNamespace(name=name) for name in (draft.get("tools") or [])]
    )


def test_new_draft_compiles():
    draft = spec_edit.new_draft("demo", tools=["search_notes"])
    spec = spec_edit.spec_from_draft(draft)
    assert spec.name == "demo"
    assert "qa" in build_workflows(spec, _stub(draft))


def test_new_draft_passes_validation():
    draft = spec_edit.new_draft("demo", tools=["search_notes"])
    assert spec_edit.draft_errors(draft, TOOLS) == []


def test_add_node_uses_block_defaults_and_breaks_reachability():
    draft = spec_edit.new_draft("demo", tools=["search_notes"])
    node_id = spec_edit.add_node(draft, "qa", "summarize")
    node = draft["workflows"]["qa"]["nodes"][-1]
    assert node["id"] == node_id
    assert node["args"] == {"max_chars": 1200}
    errors = spec_edit.draft_errors(draft, TOOLS)
    assert any("不可达" in error for error in errors)

    spec_edit.remove_node(draft, "qa", len(draft["workflows"]["qa"]["nodes"]) - 1)
    assert spec_edit.draft_errors(draft, TOOLS) == []


def test_remove_node_drops_its_edges():
    draft = spec_edit.new_draft("demo", tools=["search_notes"])
    spec_edit.remove_node(draft, "qa", 0)  # search
    edges = draft["workflows"]["qa"]["edges"]
    assert ["__start__", "search"] not in edges
    assert ["search", "answer"] not in edges


def test_required_param_missing_is_reported():
    draft = spec_edit.new_draft("demo")  # 没有工具 -> retrieve.tool 缺失
    errors = spec_edit.draft_errors(draft, TOOLS)
    assert any("retrieve.tool 是必填参数" in error for error in errors)


def test_unknown_block_is_rejected():
    draft = spec_edit.new_draft("demo", tools=["search_notes"])
    with pytest.raises(SpecError):
        spec_edit.add_node(draft, "qa", "no_such_block")


def test_workflow_crud():
    draft = spec_edit.new_draft("demo", tools=["search_notes"])
    spec_edit.add_workflow(draft, "report")
    assert "report" in draft["workflows"]
    with pytest.raises(SpecError):
        spec_edit.add_workflow(draft, "report")
    spec_edit.remove_workflow(draft, "report")
    with pytest.raises(SpecError):
        spec_edit.remove_workflow(draft, "qa")


def test_save_writes_versions_and_moves_active(tmp_path: Path):
    draft = spec_edit.new_draft("demo", tools=["search_notes"])
    first = spec_edit.save_draft(draft, root=tmp_path, tool_names=TOOLS)
    assert Path(first).name == "v1.json"

    draft["description"] = "改过的描述"
    second = spec_edit.save_draft(draft, root=tmp_path, tool_names=TOOLS)
    assert Path(second).name == "v2.json"

    rows = spec_edit.versions("demo", root=tmp_path)
    assert [row["版本"] for row in rows] == ["v1", "v2"]
    assert [row["当前"] for row in rows] == [False, True]

    old = spec_edit.load_version("demo", "v1.json", root=tmp_path)
    assert old["description"] != "改过的描述"


def test_save_refuses_invalid_draft(tmp_path: Path):
    draft = spec_edit.new_draft("demo")  # 缺必填 tool
    with pytest.raises(SpecError):
        spec_edit.save_draft(draft, root=tmp_path, tool_names=TOOLS)
    assert not (tmp_path / "demo").exists()


def test_versions_of_missing_scenario_is_empty(tmp_path: Path):
    assert spec_edit.versions("nope", root=tmp_path) == []


# ---------------------------------------------------------------- 通用 spec 场景


def _write_spec(tmp_path: Path, name: str = "demo_spec", tools=("search_notes",)) -> Path:
    root = tmp_path / "specs"
    spec_edit.save_draft(
        spec_edit.new_draft(name, tools=list(tools)), root=root, tool_names=TOOLS
    )
    return root


def test_spec_scenario_names_lists_saved_spec(tmp_path: Path):
    root = _write_spec(tmp_path)
    assert spec_scenario_names(root) == ["demo_spec"]


def test_generic_scenario_builds_from_spec(tmp_path: Path):
    root = _write_spec(tmp_path)
    scenario = build_generic_spec_scenario("demo_spec", root=root)
    assert scenario.name == "demo_spec"
    assert [tool.name for tool in scenario.tools] == ["search_notes"]
    graphs = scenario.workflow_factory(scenario)
    assert "qa" in graphs
    assert {node for node in graphs["qa"].get_graph().nodes if not node.startswith("__")} == {
        "search",
        "answer",
        "verify",
    }


def test_generic_scenario_rejects_tool_outside_pool(tmp_path: Path):
    root = tmp_path / "specs"
    draft = spec_edit.new_draft("bad", tools=["no_such_tool"])
    save_spec(spec_edit.spec_from_draft(draft), root=root)
    with pytest.raises(SpecError) as excinfo:
        build_generic_spec_scenario("bad", root=root)
    assert "no_such_tool" in str(excinfo.value)


def test_ejected_spec_is_not_listed(tmp_path: Path):
    root = _write_spec(tmp_path)
    eject("demo_spec", reason="转代码", root=root, code_root=tmp_path / "scenarios")
    assert spec_scenario_names(root) == []


def test_list_scenarios_includes_spec_names(monkeypatch):
    monkeypatch.setattr("core.scenarios.registry._spec_names", lambda: ["ui_scene"])
    assert "ui_scene" in list_scenarios()


def test_get_scenario_dispatches_to_generic(monkeypatch):
    monkeypatch.setattr("core.scenarios.registry._spec_names", lambda: ["ui_scene"])
    monkeypatch.setattr(
        "core.scenarios.generic.build_generic_spec_scenario",
        lambda name, root=None: f"built:{name}",
    )
    assert get_scenario("ui_scene") == "built:ui_scene"


def test_unknown_scenario_still_fails():
    with pytest.raises(ValueError):
        get_scenario("no_such_scenario")
