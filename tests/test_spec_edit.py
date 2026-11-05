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


# ---------------------------------------------------------------- 画布：布局与合并


def _draft() -> dict:
    return spec_edit.new_draft("demo", tools=["search_notes"])


def test_auto_layout_puts_layers_left_to_right():
    draft = _draft()
    nodes = draft["workflows"]["qa"]["nodes"]
    edges = draft["workflows"]["qa"]["edges"]
    positions = spec_edit.auto_layout(nodes, edges)
    assert positions["search"][0] < positions["answer"][0] < positions["verify"][0]
    assert positions["search"][1] == positions["answer"][1]


def test_canvas_payload_keeps_anchors_inside_board():
    payload = spec_edit.canvas_payload("demo", "qa", _draft())
    by_id = {node["id"]: node for node in payload["nodes"]}
    assert by_id["__start__"]["kind"] == "start"
    assert by_id["__end__"]["kind"] == "end"
    for node in payload["nodes"]:
        assert 0 <= node["x"] <= 1180
        assert 0 <= node["y"] <= 470


def test_anchor_positions_are_not_clamped_after_drag(tmp_path: Path):
    """START/END 拖到画布外也不能被夹回去，否则松手会回弹。"""
    draft = _draft()
    payload = {
        "nodes": [
            {"id": "search", "fn": "retrieve", "x": 300, "y": 120},
        ],
        "edges": draft["workflows"]["qa"]["edges"],
        "anchors": {"__start__": [-30, -20], "__end__": [1400, 540]},
    }
    spec_edit.absorb_canvas("demo", "qa", draft, payload, root=tmp_path)
    restored = spec_edit.canvas_payload("demo", "qa", draft, root=tmp_path)
    by_id = {node["id"]: node for node in restored["nodes"]}
    assert by_id["__start__"]["x"] == -30
    assert by_id["__start__"]["y"] == -20
    assert by_id["__end__"]["x"] == 1400
    assert by_id["__end__"]["y"] == 540


def test_canvas_payload_keeps_block_labels_when_palette_hidden():
    payload = spec_edit.canvas_payload("demo", "qa", _draft(), include_blocks=False)
    assert payload["show_palette"] is False
    assert payload["blocks"]  # 复制/粘贴要靠它给新节点中文名


def test_copy_of_inherits_args_from_source_node():
    draft = _draft()
    draft["workflows"]["qa"]["nodes"][0]["args"] = {"tool": "search_notes", "limit": 9}
    payload = {
        "nodes": [
            {"id": "search", "fn": "retrieve", "x": 0, "y": 0},
            {"id": "search-copy", "fn": "retrieve", "copy_of": "search", "x": 40, "y": 40},
        ],
        "edges": [],
    }
    spec_edit.merge_canvas(draft, "qa", payload)
    copied = next(node for node in draft["workflows"]["qa"]["nodes"] if node["id"] == "search-copy")
    assert copied["args"] == {"tool": "search_notes", "limit": 9}


def test_cut_clipboard_restores_args_after_source_removed():
    draft = _draft()
    draft["workflows"]["qa"]["nodes"] = []
    payload = {
        "nodes": [
            {"id": "search-copy", "fn": "retrieve", "copy_of": "search", "x": 40, "y": 40},
        ],
        "edges": [],
    }
    clipboard = {
        "search": {
            "id": "search",
            "fn": "retrieve",
            "args": {"tool": "search_notes", "limit": 9},
        }
    }
    spec_edit.merge_canvas(draft, "qa", payload, clipboard=clipboard)
    copied = draft["workflows"]["qa"]["nodes"][0]
    assert copied["args"] == {"tool": "search_notes", "limit": 9}


def test_merge_canvas_accepts_known_blocks():
    draft = _draft()
    payload = {
        "nodes": [
            {"id": "search", "fn": "retrieve", "x": 10, "y": 10},
            {"id": "answer", "fn": "llm_answer", "x": 200, "y": 10},
            {"id": "verify", "fn": "require_citation", "x": 400, "y": 10},
        ],
        "edges": [["__start__", "search"], ["search", "answer"], ["answer", "verify"], ["verify", "__end__"]],
    }
    assert spec_edit.merge_canvas(draft, "qa", payload) is False  # 与模板等价
    assert [node["id"] for node in draft["workflows"]["qa"]["nodes"]] == ["search", "answer", "verify"]


def test_merge_canvas_drops_unknown_block_and_dangling_edge():
    draft = _draft()
    payload = {
        "nodes": [
            {"id": "search", "fn": "retrieve", "x": 0, "y": 0},
            {"id": "ghost", "fn": "no_such_block", "x": 0, "y": 0},
        ],
        "edges": [["__start__", "search"], ["search", "ghost"], ["ghost", "__end__"]],
    }
    assert spec_edit.merge_canvas(draft, "qa", payload) is True
    workflow = draft["workflows"]["qa"]
    assert [node["id"] for node in workflow["nodes"]] == ["search"]
    assert workflow["edges"] == [["__start__", "search"]]


def test_merge_canvas_refuses_to_empty_the_workflow():
    draft = _draft()
    before = [node["id"] for node in draft["workflows"]["qa"]["nodes"]]
    assert spec_edit.merge_canvas(draft, "qa", {"nodes": [], "edges": []}) is False
    assert [node["id"] for node in draft["workflows"]["qa"]["nodes"]] == before


def test_merge_canvas_keeps_args_when_block_unchanged():
    draft = _draft()
    draft["workflows"]["qa"]["nodes"][0]["args"] = {"tool": "search_notes", "limit": 9}
    payload = {
        "nodes": [{"id": node["id"], "fn": node["fn"], "x": 0, "y": 0} for node in draft["workflows"]["qa"]["nodes"]],
        "edges": draft["workflows"]["qa"]["edges"],
    }
    spec_edit.merge_canvas(draft, "qa", payload)
    assert draft["workflows"]["qa"]["nodes"][0]["args"] == {"tool": "search_notes", "limit": 9}


def test_absorb_canvas_remembers_positions(tmp_path: Path):
    draft = _draft()
    payload = {
        "nodes": [
            {"id": "search", "fn": "retrieve", "x": 300, "y": 120},
            {"id": "answer", "fn": "llm_answer", "x": 500, "y": 120},
            {"id": "verify", "fn": "require_citation", "x": 700, "y": 120},
        ],
        "edges": draft["workflows"]["qa"]["edges"],
        "anchors": {"__start__": [40, 120], "__end__": [930, 120]},
    }
    spec_edit.absorb_canvas("demo", "qa", draft, payload, root=tmp_path)
    saved = spec_edit.load_layout("demo", tmp_path)
    assert saved["qa"]["search"] == [300, 120]
    assert saved["qa"]["__start__"] == [40, 120]

    payload2 = spec_edit.canvas_payload("demo", "qa", draft, root=tmp_path)
    by_id = {node["id"]: node for node in payload2["nodes"]}
    assert by_id["search"]["x"] == 300
    assert by_id["__end__"]["x"] == 930

    spec_edit.clear_layout("demo", "qa", tmp_path)
    assert spec_edit.load_layout("demo", tmp_path) == {}


def test_bad_node_ids_marks_only_broken_nodes():
    errors = [
        "workflow[qa].answer 从 START 不可达",
        "workflow[qa] 缺少指向 END 的边",
        "workflow[qa].verify：require_citation.args.pattern 必须是字符串",
    ]
    nodes = [{"id": "search"}, {"id": "answer"}, {"id": "verify"}]
    assert spec_edit.bad_node_ids(errors, nodes) == ["answer", "verify"]


def test_rename_node_updates_edges():
    draft = _draft()
    spec_edit.rename_node(draft, "qa", "answer", "write_answer")
    workflow = draft["workflows"]["qa"]
    assert [node["id"] for node in workflow["nodes"]] == ["search", "write_answer", "verify"]
    assert ["search", "write_answer"] in workflow["edges"]
    assert ["write_answer", "verify"] in workflow["edges"]
    with pytest.raises(SpecError):
        spec_edit.rename_node(draft, "qa", "verify", "write_answer")


def test_merge_canvas_preserves_conditional_edge_labels():
    draft = _draft()
    workflow = draft["workflows"]["qa"]
    workflow["edges"] = [
        ["__start__", "search"],
        ["search", "answer", "hit"],
        ["search", "verify", "miss"],
        ["answer", "__end__"],
        ["verify", "__end__"],
    ]
    payload = spec_edit.canvas_payload("demo", "qa", draft)
    assert ["search", "answer", "hit"] in payload["edges"]
    # 模拟画布只回传 from/to（条件标签不在画布 DOM 里）
    payload["edges"] = [[edge[0], edge[1]] for edge in payload["edges"]]
    spec_edit.merge_canvas(draft, "qa", payload)
    assert ["search", "answer", "hit"] in workflow["edges"]
    assert ["search", "verify", "miss"] in workflow["edges"]
