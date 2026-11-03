# -*- coding: utf-8 -*-
from core.agent.workflow import WorkflowRuntime
from core.scenarios.registry import get_scenario, list_scenarios


def test_new_scenarios_are_registered():
    names = set(list_scenarios())
    assert {"workspace_assistant", "research_assistant", "router"} <= names


def test_workspace_assistant_tools_and_workflows():
    scenario = get_scenario("workspace_assistant")
    tools = {tool.name for tool in scenario.tools}
    assert {"search_notes", "write_note", "remember", "translate", "summarize"} <= tools
    runtime = WorkflowRuntime(scenario)
    assert {"document_qa", "study_notes", "cross_lingual", "content_draft"} <= set(
        runtime.list_workflows()
    )


def test_research_assistant_tools_and_workflow():
    scenario = get_scenario("research_assistant")
    tools = {tool.name for tool in scenario.tools}
    assert {"list_sources", "read_source", "search_sources", "write_report", "subagent"} <= tools
    runtime = WorkflowRuntime(scenario)
    assert "deep_research" in runtime.list_workflows()


def test_router_tools():
    scenario = get_scenario("router")
    tools = {tool.name for tool in scenario.tools}
    assert {
        "route_to_workspace",
        "route_to_coding",
        "route_to_robot",
        "route_to_research",
    } <= tools
