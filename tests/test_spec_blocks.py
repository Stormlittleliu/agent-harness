# -*- coding: utf-8 -*-
"""新块与路由表：call_tool / llm_text / fan_out，以及 data/routes 的读写与校验。"""
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

from core.scenarios.router import routes as route_table
from core.scenarios.spec_nodes import call_tool, fan_out, llm_text, render_template


class _FakeModel:
    def invoke(self, messages):
        return AIMessage(content=f"model:{messages[-1][1][:12]}")


class _FakeScenario:
    def __init__(self):
        @tool("lookup")
        def lookup(query: str) -> str:
            """查一下。"""
            return f"found:{query}"

        @tool("subagent")
        def subagent(description: str) -> str:
            """读资料并回答。"""
            return f"sub:{description[:6]}"

        self.model = _FakeModel()
        self.system_prompt = "sys"
        self._tools = {"lookup": lookup, "subagent": subagent}

    def get_tool(self, name):
        return self._tools[name]


def test_render_template_reads_state_and_scratch():
    state = {"input": "问题", "scratch": {"user_id": "u-1"}}
    assert render_template("{input}/{scratch.user_id}/{missing}", state) == "问题/u-1/"


def test_call_tool_interpolates_args_and_saves():
    scenario = _FakeScenario()
    out = call_tool(
        {"input": "滤网", "scratch": {}},
        scenario=scenario,
        tool="lookup",
        args='{"query": "{input}"}',
        save_to="answer",
    )
    assert out["answer"] == "found:滤网"


def test_call_tool_writes_scratch_key():
    scenario = _FakeScenario()
    out = call_tool(
        {"scratch": {}},
        scenario=scenario,
        tool="lookup",
        args='{"query": "x"}',
        save_to="scratch.records",
    )
    assert out["scratch"]["records"] == "found:x"


def test_call_tool_rejects_bad_json():
    out = call_tool({"scratch": {}}, scenario=_FakeScenario(), tool="lookup", args="{oops", save_to="answer")
    assert "不是合法 JSON" in out["scratch"]["error"]


def test_llm_text_renders_prompt():
    out = llm_text(
        {"answer": "草稿", "scratch": {}},
        scenario=_FakeScenario(),
        prompt="复查：{answer}",
        save_to="scratch.verified",
    )
    assert out["scratch"]["verified"] == "model:复查：草稿"


def test_fan_out_merges_subagent_results():
    out = fan_out(
        {"scratch": {"queries": "子问题一\n子问题二"}},
        scenario=_FakeScenario(),
        subagent="subagent",
        queries_from="scratch.queries",
        save_to="scratch.findings",
    )
    findings = out["scratch"]["findings"]
    assert "子问题一" in findings and "子问题二" in findings
    assert "sub:" in findings


def test_fan_out_without_queries_reports_error():
    out = fan_out({"scratch": {}}, scenario=_FakeScenario(), queries_from="scratch.queries")
    assert "没有子问题" in out["scratch"]["error"]


def test_route_table_validates_targets():
    good = route_table.default_routes()
    known = [item["target"] for item in good]
    assert route_table.validate_routes(good, known_scenarios=known) == []

    bad = [{"target": "router", "tool": "route_to_me", "strong": ["x"]}]
    errors = route_table.validate_routes(bad, known_scenarios=["router"], self_name="router")
    assert any("递归" in error for error in errors)

    unknown = [{"target": "ghost", "tool": "route_to_ghost", "strong": ["x"]}]
    assert any("不存在" in error for error in route_table.validate_routes(unknown, known_scenarios=known))


def test_route_table_builds_tools_and_policy():
    table = route_table.default_routes()
    tools = route_table.build_route_tools(table)
    assert [tool.name for tool in tools][:1] == ["route_to_workspace"]
    policy = route_table.build_policy(table)
    assert [rule.tool for rule in policy.rules] == [item["tool"] for item in table]


def test_router_spec_uses_route_table():
    """router 的 spec 里工具清单必须和路由表一致，改表不用改 spec。"""
    from core.scenarios.registry import get_scenario

    scenario = get_scenario("router")
    table = route_table.load_routes("router")
    assert [tool.name for tool in scenario.tools] == [item["tool"] for item in table]
    assert scenario.kind == "router"
    assert scenario.system_prompt.count("-> route_to_") == len(table)

def test_branch_and_constant_blocks():
    from core.scenarios.spec_nodes import branch, constant

    hit = branch({"tool_result": "资料不足，无法确定"}, mode="keywords", keywords=["资料不足"], hit="refuse", miss="ok")
    assert hit["scratch"]["route"] == "refuse"

    miss = branch({"tool_result": "有资料"}, mode="keywords", keywords=["资料不足"], hit="refuse", miss="ok")
    assert miss["scratch"]["route"] == "ok"

    empty = branch({"tool_result": "  "}, mode="empty", hit="refuse", miss="ok")
    assert empty["scratch"]["route"] == "refuse"

    fixed = constant({"input": "x"}, text="资料中没有找到足够信息，无法确定。")
    assert fixed["answer"].startswith("资料中")


def test_conditional_edges_compile_and_validate():
    from core.scenarios.spec import SpecError, build_workflows, spec_from_dict, validate_spec

    data = {
        "schema_version": 1,
        "name": "branch_demo",
        "tools": [],
        "workflows": {
            "qa": {
                "nodes": [
                    {"id": "probe", "fn": "constant", "args": {"text": "资料不足"}},
                    {"id": "branch", "fn": "branch", "args": {"mode": "keywords", "field": "answer", "keywords": ["资料不足"], "hit": "refuse", "miss": "done"}},
                    {"id": "refuse", "fn": "constant", "args": {"text": "无法确定"}},
                    {"id": "done", "fn": "constant", "args": {"text": "ok"}},
                ],
                "edges": [
                    ["__start__", "probe"],
                    ["probe", "branch"],
                    ["branch", "refuse", "refuse"],
                    ["branch", "done", "done"],
                    ["refuse", "__end__"],
                    ["done", "__end__"],
                ],
            }
        },
    }
    spec = spec_from_dict(data)
    assert validate_spec(spec) == []
    compiled = build_workflows(spec, type("S", (), {"tools": []})())
    assert "qa" in compiled

    mixed = dict(data)
    mixed["workflows"] = {
        "qa": {
            "nodes": data["workflows"]["qa"]["nodes"],
            "edges": [
                ["__start__", "probe"],
                ["probe", "branch"],
                ["branch", "refuse", "refuse"],
                ["branch", "done", "done"],
                ["branch", "__end__"],
            ],
        }
    }
    errors = validate_spec(spec_from_dict(mixed))
    assert any("同时有条件和无条件出边" in error for error in errors)
