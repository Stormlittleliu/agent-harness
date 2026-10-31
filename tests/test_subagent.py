# -*- coding: utf-8 -*-
from langchain_core.messages import AIMessage
from langchain_core.tools import tool

import core.agent.subagent as subagent_module
from core.agent.subagent import build_subagent_tool, select_subagent_tools
from core.runtime.config import SubagentConfig


@tool("read_file")
def read_file(path: str) -> str:
    """Read a file."""
    return path


@tool("glob")
def glob(pattern: str) -> str:
    """Glob files."""
    return pattern


@tool("create_task")
def create_task(subject: str) -> str:
    """Create a task."""
    return subject


@tool("subagent")
def subagent(description: str) -> str:
    """Spawn a subagent."""
    return description


def test_select_tools_excludes_nested_subagent_and_task_tools():
    config = SubagentConfig(allowed_tools=["read_file", "glob"])
    parent = [read_file, glob, create_task, subagent]
    names = [tool.name for tool in select_subagent_tools(parent, config)]
    assert names == ["read_file", "glob"]


def test_default_subagent_tool_has_expected_name():
    config = SubagentConfig(allowed_tools=["read_file"])
    tool_obj = build_subagent_tool(None, [read_file, subagent], config)
    assert tool_obj.name == "subagent"
    assert "子 Agent" in tool_obj.description


def test_subagent_spawns_filtered_child_with_fresh_context(monkeypatch):
    class FakeAgent:
        last_scenario = None
        last_query = None
        last_thread = None

        def __init__(self, scenario):
            self.scenario = scenario
            FakeAgent.last_scenario = scenario

        def invoke(self, query, thread_id=None):
            FakeAgent.last_query = query
            FakeAgent.last_thread = thread_id
            return {"messages": [AIMessage(content="child summary")]}

    monkeypatch.setattr(subagent_module, "FrameworkAgent", FakeAgent)
    config = SubagentConfig(allowed_tools=["read_file"])
    tool_obj = build_subagent_tool(None, [read_file, create_task, subagent], config)

    result = tool_obj.invoke({"description": "inspect workspace"})

    assert result == "child summary"
    assert FakeAgent.last_query == "inspect workspace"
    child = FakeAgent.last_scenario
    assert child.name == "subagent_child"
    assert child.checkpoint is False
    assert [item.name for item in child.tools] == ["read_file"]
