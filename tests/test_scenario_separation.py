# -*- coding: utf-8 -*-
"""架构边界守卫：场景工具、LangGraph 工作流与 MCP 保持分离。

- core/agent/ 不依赖具体场景，也不依赖 MCP；
- 只有 mcp_demo 场景加载 core.mcp；
- robot_vacuum 的 LangGraph 节点只通过 Scenario.get_tool 取工具；
- coding_demo 的工作区工具不包含 MCP 工具。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _python_files(folder: Path):
    for path in folder.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path, path.read_text(encoding="utf-8")


def test_agent_layer_has_no_scenario_or_mcp_imports():
    for path, text in _python_files(ROOT / "core" / "agent"):
        assert "core.scenarios" not in text, f"agent 层不应依赖场景：{path}"
        assert "core.mcp" not in text, f"agent 层不应依赖 MCP：{path}"


def test_only_mcp_demo_imports_mcp():
    for path, text in _python_files(ROOT / "core" / "scenarios"):
        if path.parent.name == "mcp_demo":
            continue
        # pools.py 是工具箱注册表：它替 mcp_demo 的 spec 仿造版保管 MCP 工具。
        # 除它之外，只有 mcp_demo 自己可以加载 MCP。
        if path.name == "pools.py":
            assert "core.mcp.client" in text
            continue
        assert "core.mcp" not in text, f"只有 mcp_demo 可以加载 MCP：{path}"

    mcp_text = (ROOT / "core" / "scenarios" / "mcp_demo" / "scenario.py").read_text(
        encoding="utf-8"
    )
    assert "core.mcp.client" in mcp_text
    assert "workflow_factory=None" in mcp_text


def test_langgraph_workflow_uses_scenario_tool_registry():
    text = (ROOT / "core" / "scenarios" / "robot_vacuum" / "graph.py").read_text(
        encoding="utf-8"
    )
    assert "scenario.get_tool" in text
    assert "core.mcp" not in text
    assert "core.tools.business" not in text
    assert "core.tools.rag" not in text
    for tool_name in ("rag_summarize", "get_user_id", "get_current_month", "fetch_external_data"):
        assert f'"{tool_name}"' in text
