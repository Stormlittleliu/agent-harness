# -*- coding: utf-8 -*-
"""spec 场景：校验、编译、版本化读写、节点函数。

这些用例不调用模型、不读 Chroma，保持确定性。
"""
import json

import pytest

from core.scenarios.spec import (
    END,
    START,
    ScenarioSpec,
    SpecError,
    active_spec_path,
    build_from_spec,
    build_workflows,
    load_active_spec,
    load_spec,
    save_spec,
    spec_to_dict,
    validate_spec,
)
from core.scenarios.spec_nodes import (
    NODE_PARAMS,
    NODE_REGISTRY,
    block_params,
    react_loop,
    registered_nodes,
    require_citation,
    retrieve,
    summarize,
    write_report,
)


class _FakeTool:
    def __init__(self, name="search_notes", content="[note-1] 机器人回充失败先检查充电座"):
        self.name = name
        self.content = content
        self.calls = []

    def invoke(self, payload):
        self.calls.append(payload)
        return type("_Result", (), {"content": self.content})()


class _FakeScenario:
    name = "fake"
    system_prompt = "你是测试助手。"
    model = None

    def __init__(self, tool=None):
        self._tool = tool or _FakeTool()
        self.tools = [self._tool]

    def get_tool(self, name):
        if name == self._tool.name:
            return self._tool
        raise KeyError(name)


def _payload(**overrides):
    data = {
        "schema_version": 1,
        "name": "flow_demo",
        "description": "测试用 spec 场景",
        "tools": ["search_notes"],
        "system_prompt": "你是办公助手，回答必须带 [笔记id] 引用。",
        "harness": {"enable_todo": False},
        "workflows": {
            "qa": {
                "nodes": [
                    {"id": "search", "fn": "retrieve", "args": {"tool": "search_notes"}},
                    {"id": "answer", "fn": "llm_answer"},
                    {"id": "verify", "fn": "require_citation"},
                ],
                "edges": [
                    [START, "search"],
                    ["search", "answer"],
                    ["answer", "verify"],
                    ["verify", END],
                ],
            }
        },
    }
    data.update(overrides)
    return data


def _spec(**overrides) -> ScenarioSpec:
    return ScenarioSpec.model_validate(_payload(**overrides))


# ---------------------------------------------------------------- 注册表


def test_six_blocks_are_registered_with_params():
    expected = {"retrieve", "llm_answer", "require_citation", "summarize", "write_report", "react_loop"}
    assert expected <= set(registered_nodes())
    assert set(NODE_PARAMS) == set(NODE_REGISTRY)
    for name in NODE_REGISTRY:
        assert callable(NODE_REGISTRY[name])
        assert block_params(name), f"{name} 没有声明参数契约"


# ---------------------------------------------------------------- 校验


def test_valid_spec_has_no_errors():
    assert validate_spec(_spec()) == []


def test_unknown_node_function_is_rejected():
    payload = _payload()
    payload["workflows"]["qa"]["nodes"][0]["fn"] = "nope"
    errors = validate_spec(ScenarioSpec.model_validate(payload))
    assert any("未注册的块" in error for error in errors)


def test_dangling_edge_is_rejected():
    payload = _payload()
    payload["workflows"]["qa"]["edges"].append(["answer", "missing"])
    errors = validate_spec(ScenarioSpec.model_validate(payload))
    assert any("边终点不存在：missing" in error for error in errors)


def test_unreachable_node_is_rejected():
    payload = _payload()
    payload["workflows"]["qa"]["nodes"].append({"id": "orphan", "fn": "require_citation"})
    payload["workflows"]["qa"]["edges"].append(["orphan", END])
    errors = validate_spec(ScenarioSpec.model_validate(payload))
    assert any("orphan 从 START 不可达" in error for error in errors)


def test_workflow_without_end_is_rejected():
    payload = _payload()
    payload["workflows"]["qa"]["edges"] = [
        [START, "search"],
        ["search", "answer"],
    ]
    errors = validate_spec(ScenarioSpec.model_validate(payload))
    assert any("缺少指向 END 的边" in error for error in errors)
    assert any("走不到 END" in error for error in errors)


def test_duplicate_node_id_is_rejected():
    payload = _payload()
    payload["workflows"]["qa"]["nodes"].append({"id": "search", "fn": "llm_answer"})
    errors = validate_spec(ScenarioSpec.model_validate(payload))
    assert any("节点 id 重复" in error for error in errors)


def test_schema_version_mismatch_is_rejected():
    errors = validate_spec(_spec(schema_version=2))
    assert any("schema_version" in error for error in errors)


def test_reserved_node_args_are_rejected():
    payload = _payload()
    payload["workflows"]["qa"]["nodes"][0]["args"] = {"tool": "search_notes", "scenario": 1}
    errors = validate_spec(ScenarioSpec.model_validate(payload))
    assert any("参数名被保留" in error for error in errors)


def test_unknown_extra_field_is_rejected():
    with pytest.raises(Exception):
        ScenarioSpec.model_validate(_payload(tools_typo=["x"]))


# ---------------------------------------------------------------- 编译


def test_build_workflows_compiles_spec():
    graphs = build_workflows(_spec(), _FakeScenario())
    assert set(graphs) == {"qa"}
    graph = graphs["qa"].get_graph()
    assert {"search", "answer", "verify"} <= set(graph.nodes)
    edges = {(edge.source, edge.target) for edge in graph.edges}
    assert (START, "search") in edges
    assert ("verify", END) in edges


def test_build_workflows_raises_on_invalid_spec():
    payload = _payload()
    payload["workflows"]["qa"]["edges"].append(["answer", "missing"])
    with pytest.raises(SpecError) as excinfo:
        build_workflows(ScenarioSpec.model_validate(payload), _FakeScenario())
    assert any("missing" in error for error in excinfo.value.errors)


def test_build_from_spec_filters_tools_and_exposes_factory():
    extra = _FakeTool(name="read_note", content="[note-2] 无关工具")
    spec = _spec()
    scenario = build_from_spec(
        spec,
        tools=[_FakeTool(), extra],
        model=None,
        checkpoint_backend="memory",
    )
    assert scenario.name == "flow_demo"
    assert [tool.name for tool in scenario.tools] == ["search_notes"]
    assert scenario.enable_todo is False
    graphs = scenario.workflow_factory(scenario)
    assert set(graphs) == {"qa"}


def test_build_from_spec_rejects_missing_tool():
    spec = _spec(tools=["search_notes", "not_exist"])
    with pytest.raises(SpecError) as excinfo:
        build_from_spec(spec, tools=[_FakeTool()], model=None)
    assert any("not_exist" in error for error in excinfo.value.errors)


# ---------------------------------------------------------------- 读写


def test_save_load_roundtrip(tmp_path):
    spec = _spec()
    path = save_spec(spec, root=tmp_path)
    assert path == tmp_path / "flow_demo" / "v1.json"
    assert load_spec(path) == spec
    assert load_active_spec("flow_demo", root=tmp_path) == spec
    assert active_spec_path("flow_demo", root=tmp_path) == path


def test_save_increments_version_and_moves_active(tmp_path):
    save_spec(_spec(), root=tmp_path)
    second = save_spec(_spec(description="第二版"), root=tmp_path)
    assert second.name == "v2.json"
    active = json.loads((tmp_path / "flow_demo" / "active.json").read_text(encoding="utf-8"))
    assert active == {"version": 2, "file": "v2.json"}
    assert load_active_spec("flow_demo", root=tmp_path).description == "第二版"


def test_load_active_spec_returns_none_without_pointer(tmp_path):
    assert active_spec_path("flow_demo", root=tmp_path) is None
    assert load_active_spec("flow_demo", root=tmp_path) is None


def test_spec_to_dict_is_json_ready():
    payload = spec_to_dict(_spec())
    assert payload["schema_version"] == 1
    assert payload["workflows"]["qa"]["edges"][0] == [START, "search"]
    json.dumps(payload, ensure_ascii=False)


# ---------------------------------------------------------------- 节点


def test_retrieve_writes_tool_result():
    scenario = _FakeScenario()
    state = {"input": "回充失败怎么办"}
    result = retrieve(state, scenario=scenario, tool="search_notes")
    assert "[note-1]" in result["tool_result"]
    assert result["scratch"]["error"] is None
    assert scenario.get_tool("search_notes").calls[0]["args"]["query"] == "回充失败怎么办"


def test_retrieve_without_tool_reports_error():
    result = retrieve({"input": "x"}, scenario=_FakeScenario(), tool="")
    assert result["tool_result"] == ""
    assert "tool" in result["scratch"]["error"]


def test_require_citation_flags_missing_reference():
    assert require_citation({"answer": "直接回答，没有引用"})["scratch"]["error"]
    assert require_citation({"answer": "见 [note-1]"})["scratch"]["error"] is None


def test_summarize_truncates():
    text = "x" * 50
    assert summarize({"tool_result": text}, max_chars=10)["tool_result"].startswith("x" * 10)
    assert summarize({"tool_result": "short"}, max_chars=10)["tool_result"] == "short"


def test_write_report_rejects_path_escape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    blocked = write_report({"answer": "hi"}, path="../evil.md")
    assert "非法路径" in blocked["scratch"]["error"]
    assert not (tmp_path / "evil.md").exists()

    ok = write_report({"answer": "hi"}, path="sub/ok.md")
    target = tmp_path / "data" / "runtime" / "spec_reports" / "sub" / "ok.md"
    assert target.read_text(encoding="utf-8") == "hi"
    assert ok["scratch"]["written"].endswith("ok.md")


# ---------------------------------------------------------------- 参数契约


def test_unknown_block_arg_is_rejected():
    payload = _payload()
    payload["workflows"]["qa"]["nodes"][0]["args"] = {"tool": "search_notes", "nope": 1}
    errors = validate_spec(ScenarioSpec.model_validate(payload))
    assert any("不认识参数 nope" in error for error in errors)


def test_missing_required_block_arg_is_rejected():
    payload = _payload()
    payload["workflows"]["qa"]["nodes"][0]["args"] = {}
    errors = validate_spec(ScenarioSpec.model_validate(payload))
    assert any("tool 是必填参数" in error for error in errors)


def test_wrong_param_type_is_rejected():
    payload = _payload()
    payload["workflows"]["qa"]["nodes"][0]["args"] = {"tool": "search_notes", "limit": "5"}
    errors = validate_spec(ScenarioSpec.model_validate(payload))
    assert any("limit 必须是整数" in error for error in errors)


def test_param_range_is_enforced():
    payload = _payload()
    payload["workflows"]["qa"]["nodes"][0]["args"] = {"tool": "search_notes", "limit": 99}
    errors = validate_spec(ScenarioSpec.model_validate(payload))
    assert any("limit 不能大于 20" in error for error in errors)


def test_enum_param_rejects_unknown_choice():
    payload = _payload()
    payload["workflows"]["qa"]["nodes"] = [
        {"id": "search", "fn": "retrieve", "args": {"tool": "search_notes"}},
        {
            "id": "agent",
            "fn": "react_loop",
            "args": {"tools": ["search_notes"], "stop_when": "never"},
        },
    ]
    payload["workflows"]["qa"]["edges"] = [[START, "search"], ["search", "agent"], ["agent", END]]
    errors = validate_spec(ScenarioSpec.model_validate(payload))
    assert any("stop_when 必须是" in error for error in errors)


def test_tool_refs_checked_only_with_known_tools():
    payload = _payload()
    payload["workflows"]["qa"]["nodes"] = [
        {"id": "agent", "fn": "react_loop", "args": {"tools": ["ghost_tool"]}},
    ]
    payload["workflows"]["qa"]["edges"] = [[START, "agent"], ["agent", END]]
    spec = ScenarioSpec.model_validate(payload)

    assert not any("ghost_tool" in error for error in validate_spec(spec))
    errors = validate_spec(spec, tool_names={"search_notes"})
    assert any("ghost_tool" in error for error in errors)


def test_build_from_spec_rejects_tool_ref_outside_whitelist():
    payload = _payload()
    payload["workflows"]["qa"]["nodes"] = [
        {"id": "agent", "fn": "react_loop", "args": {"tools": ["read_note"]}},
    ]
    payload["workflows"]["qa"]["edges"] = [[START, "agent"], ["agent", END]]
    spec = ScenarioSpec.model_validate(payload)

    with pytest.raises(SpecError) as excinfo:
        build_from_spec(spec, tools=[_FakeTool(), _FakeTool(name="read_note")], model=None)
    assert any("read_note" in error for error in excinfo.value.errors)


def test_param_defaults_match_function_signatures():
    import inspect

    for fn_name, params in NODE_PARAMS.items():
        signature = inspect.signature(NODE_REGISTRY[fn_name])
        for param in params:
            if param.default is None:
                continue
            assert signature.parameters[param.name].default == param.default, fn_name


def test_react_loop_without_tools_reports_error():
    result = react_loop({"input": "x"}, scenario=_FakeScenario(), tools=[])
    assert "没有配置工具" in result["scratch"]["error"]


def test_react_loop_unknown_tool_reports_error():
    result = react_loop({"input": "x"}, scenario=_FakeScenario(), tools=["ghost"])
    assert "不存在的工具" in result["scratch"]["error"]


# ---------------------------------------------------------------- 策略覆盖


def test_policies_are_validated_and_passed_through():
    spec = ScenarioSpec.model_validate(
        _payload(policies=[{"name": "retry", "enabled": False, "reason": "演示场景不需要重试"}])
    )
    assert validate_spec(spec) == []

    scenario = build_from_spec(spec, tools=[_FakeTool()], model=None)
    assert scenario.policies == [
        {"name": "retry", "enabled": False, "args": {}, "reason": "演示场景不需要重试"}
    ]


def test_unknown_policy_is_rejected_by_spec():
    spec = ScenarioSpec.model_validate(_payload(policies=[{"name": "telepathy"}]))
    errors = validate_spec(spec)
    assert any("未知策略" in error for error in errors)


def test_disabled_policy_requires_reason_in_spec():
    spec = ScenarioSpec.model_validate(_payload(policies=[{"name": "retry", "enabled": False}]))
    errors = validate_spec(spec)
    assert any("reason" in error for error in errors)
