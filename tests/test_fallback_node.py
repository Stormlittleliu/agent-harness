# -*- coding: utf-8 -*-
"""兜底检索回答块的离线测试：合并候选库、全空拒答、单库失败、参数名适配。"""
from langchain_core.messages import AIMessage

from core.scenarios.spec_nodes import (
    FALLBACK_EMPTY,
    fallback_answer,
    validate_args,
    validate_tool_refs,
)


class _FakeTool:
    def __init__(self, name: str, text: str, schema: dict | None = None, boom: bool = False):
        self.name = name
        self._text = text
        self._boom = boom
        self.args = schema if schema is not None else {"query": "str"}
        self.seen: dict | None = None

    def invoke(self, payload):
        self.seen = payload["args"]
        if self._boom:
            raise RuntimeError("库挂了")
        return self._text


class _FakeModel:
    def __init__(self, text: str = "回答 [1]"):
        self._text = text
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        return AIMessage(content=self._text)


class _Scenario:
    def __init__(self, tools, model=None):
        self._tools = {tool.name: tool for tool in tools}
        self.model = model
        self.system_prompt = "你是零售客服。"

    def get_tool(self, name):
        return self._tools[name]


def test_fallback_merges_candidate_sources_and_uses_k():
    robot = _FakeTool("robot_retrieve", "滤网两个月换一次 [r1]", {"query": "str", "k": "int"})
    clothing = _FakeTool("clothing_retrieve", "尺码按身高选 [c1]", {"query": "str", "k": "int"})
    scenario = _Scenario([robot, clothing], model=_FakeModel("先换滤网 [r1]"))
    state = {"input": "客厅那个设备最近味道大，顺便问下衣服尺码"}

    update = fallback_answer(state, scenario, tools=["robot_retrieve", "clothing_retrieve"], limit=3)

    assert update["answer"] == "先换滤网 [r1]"
    assert "【robot_retrieve】" in update["tool_result"]
    assert "【clothing_retrieve】" in update["tool_result"]
    assert update["scratch"]["fallback_sources"] == {"robot_retrieve": 1, "clothing_retrieve": 1}
    # RAG 工具收 k，不能写成 limit
    assert robot.seen == {"query": state["input"], "k": 3}


def test_fallback_refuses_without_any_material():
    empty = _FakeTool("robot_retrieve", "   ")
    scenario = _Scenario([empty], model=_FakeModel())
    update = fallback_answer({"input": "换个灯"}, scenario, tools=["robot_retrieve"])

    assert update["answer"] == FALLBACK_EMPTY
    assert update["scratch"]["error"] == "候选库都没有检索到内容"
    assert scenario.model.calls == 0  # 没材料就不叫模型


def test_fallback_survives_one_broken_tool():
    broken = _FakeTool("robot_retrieve", "", boom=True)
    ok = _FakeTool("clothing_retrieve", "棉质外套不要机洗 [c2]")
    scenario = _Scenario([broken, ok], model=_FakeModel("不要机洗 [c2]"))
    update = fallback_answer({"input": "外套怎么洗"}, scenario, tools=["robot_retrieve", "clothing_retrieve"])

    assert update["answer"] == "不要机洗 [c2]"
    assert "robot_retrieve" in update["scratch"]["error"]
    assert update["scratch"]["fallback_sources"]["clothing_retrieve"] == 1


def test_fallback_requires_tools():
    update = fallback_answer({"input": "随便问问"}, _Scenario([]), tools=[])
    assert update["answer"] == ""
    assert "没有配置 tools" in update["scratch"]["error"]


def test_fallback_args_contract_rejects_unknown_tool():
    assert validate_args("fallback_answer", {"tools": ["clothing_retrieve"]}) == []
    assert validate_args("fallback_answer", {}) != []
    errors = validate_tool_refs("fallback_answer", {"tools": ["ghost"]}, {"clothing_retrieve"})
    assert any("ghost" in error for error in errors)
