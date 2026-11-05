# -*- coding: utf-8 -*-
"""工具箱：每个场景"能看见哪些工具"的唯一来源。

为什么单独一层：场景的实现方式有两种（代码 / spec），但**工具永远来自代码**。
把工具组装收进这里之后：

- 代码场景和它的 spec 仿造版用同一个工具箱，不会出现"仿造版少了个工具"；
- spec 只需要写 ``tools: [...]`` 白名单，不关心工具怎么造出来；
- 界面上的工具下拉框也从这里取，不再各自猜。

池子里没有的场景（控制台里新建的）走 ``office`` 兜底。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.llm.factory import chat_model
from core.scenarios.workspace_assistant.tools import (
    MemoryStore,
    NoteStore,
    build_workspace_tools,
)
from core.utils.path_tool import get_abs_path

WORKSPACE_SEED = Path(get_abs_path("data/workspace_assistant/notes"))
WORKSPACE_USER = Path(get_abs_path("data/runtime/workspace_assistant/notes"))
WORKSPACE_DB = Path(get_abs_path("data/runtime/workspace_assistant/memory.sqlite"))

SPEC_USER = Path(get_abs_path("data/runtime/spec_scenarios/notes"))
SPEC_DB = Path(get_abs_path("data/runtime/spec_scenarios/memory.sqlite"))

CODING_WORKSPACE = Path(get_abs_path("data/runtime/coding_workspace"))
CODING_LOG_DIR = Path(get_abs_path("data/runtime/run_window"))
CODING_TASK_DB = Path(get_abs_path("data/runtime/tasks/coding_demo.sqlite"))

RESEARCH_SOURCES = Path(get_abs_path("data/research_assistant/sources"))
RESEARCH_REPORTS = Path(get_abs_path("data/runtime/research_assistant/reports"))
RESEARCH_LOG_DIR = Path(get_abs_path("data/runtime/research_assistant/run_window"))


@dataclass(frozen=True)
class Toolbox:
    """一个场景的工具集合，外加它需要的运行时与"代码层默认值"。

    ``defaults`` 是 ``Scenario`` 字段的覆盖层（tool_policy / high_risk_tools /
    pii_types / context / timeouts / checkpoint…）。它们属于"实现"，不该写进 spec；
    spec 只描述结构（提示词 / 工具白名单 / 拓扑 / harness 开关）。
    """

    name: str
    tools: tuple = ()
    runtime: Any = None
    middleware: tuple = ()
    defaults: dict = field(default_factory=dict)
    notes: tuple[str, ...] = field(default_factory=tuple)


def _notes_tools(seed: Path, user: Path, db: Path) -> tuple:
    store = NoteStore(seed, user)
    memory = MemoryStore(db)
    return tuple(build_workspace_tools(store, memory))


def _office() -> Toolbox:
    """通用兜底池：笔记检索 / 读写 / 长期记忆 / 翻译 / 总结。"""
    return Toolbox("office", _notes_tools(WORKSPACE_SEED, SPEC_USER, SPEC_DB))


def _workspace_assistant() -> Toolbox:
    from core.agent.middleware import log_before_model, monitor_tool

    return Toolbox(
        "workspace_assistant",
        _notes_tools(WORKSPACE_SEED, WORKSPACE_USER, WORKSPACE_DB),
        middleware=(monitor_tool, log_before_model),
        defaults={
            "middleware": [monitor_tool, log_before_model],
            "pii_types": ["email", "credit_card", "ip"],
            "tool_policy": {
                "default": "allow",
                "risk_levels": {
                    "list_notes": "low",
                    "read_note": "low",
                    "search_notes": "low",
                    "write_note": "medium",
                    "remember": "medium",
                    "recall": "low",
                    "list_memory": "low",
                    "translate": "low",
                    "summarize": "low",
                },
            },
            "tool_timeout_seconds": 30,
            "tool_timeouts": {"translate": 60, "summarize": 60},
            "checkpoint_backend": "sqlite",
            "checkpoint_path": "data/runtime/workspace_assistant_checkpoints.sqlite",
        },
    )


def _general() -> Toolbox:
    return Toolbox("general")


def _structured_demo() -> Toolbox:
    return Toolbox("structured_demo")


def _coding_demo() -> Toolbox:
    from core.agent.subagent import build_subagent_tool
    from core.runtime.config import RuntimeConfig, SubagentConfig
    from core.runtime.task_tools import build_task_tools
    from core.runtime.tasks import TaskStore
    from core.runtime.workspace import Workspace, build_workspace_tools
    from core.scenarios.coding_demo.hooks import hooks

    workspace = Workspace(CODING_WORKSPACE, CODING_LOG_DIR)
    readme = workspace.root / "README.md"
    if not readme.exists():
        readme.write_text("# Demo Workspace\n\n这是一个 coding agent 演示工作区。\n", encoding="utf-8")
    hello = workspace.root / "hello.py"
    if not hello.exists():
        hello.write_text('print("hello from demo workspace")\n', encoding="utf-8")

    store = TaskStore(CODING_TASK_DB)
    subagent = SubagentConfig(
        allowed_tools=["read_file", "glob", "grep", "run_command"],
        max_model_calls=12,
        token_budget=20000,
        timeout_seconds=120,
    )
    runtime = RuntimeConfig(
        workspace=workspace.root,
        task_store_path=CODING_TASK_DB,
        log_dir=CODING_LOG_DIR,
        task_store=store,
        subagent=subagent,
        hooks=hooks(),
    )
    tools = build_workspace_tools(workspace) + build_task_tools(store)
    subagent_tool = build_subagent_tool(chat_model, tools, subagent, parent_runtime=runtime)
    return Toolbox("coding_demo", tuple(tools) + (subagent_tool,), runtime=runtime)


def _robot_vacuum() -> Toolbox:
    from core.agent.middleware import (
        LimitStepsMiddleware,
        ValidateToolArgsMiddleware,
        log_before_model,
        monitor_tool,
    )
    from core.scenarios.robot_vacuum.middleware import (
        IntentRouterMiddleware,
        ReportPromptSwitchMiddleware,
    )
    from core.scenarios.robot_vacuum.validators import VALIDATORS
    from core.tools.business.tools import (
        configure_business_tools,
        fetch_external_data,
        get_current_month,
        get_user_id,
        get_user_location,
        get_weather,
        reset_device,
    )
    from core.tools.rag.tools import build_rag_tools
    from core.utils.config_handler import load_agent_config

    agent_yml = get_abs_path("core/scenarios/robot_vacuum/config/agent.yml")
    prompts_yml = get_abs_path("core/scenarios/robot_vacuum/config/prompts.yml")
    config = load_agent_config(agent_yml)
    configure_business_tools(config.get("external_data_path"))
    policy = config.get("tool_policy", {}) or {}
    approval = policy.get("require_approval") or ["reset_device"]
    rag_summarize, _ = build_rag_tools(where={"domain": "robot"})
    tools = (
        rag_summarize,
        get_weather,
        get_user_location,
        get_user_id,
        get_current_month,
        fetch_external_data,
        reset_device,
    )
    middleware = (
        monitor_tool,
        ValidateToolArgsMiddleware(VALIDATORS),
        IntentRouterMiddleware((config.get("intent", {}) or {}).get("report_keywords", [])),
        log_before_model,
        LimitStepsMiddleware(int(config.get("max_model_calls", 5))),
        ReportPromptSwitchMiddleware(prompts_yml),
    )
    defaults = {
        "middleware": list(middleware),
        # 中间件之间通过 context 共享 intent；空字典会被 LangGraph 丢弃。
        "context": {"intent": None},
        "high_risk_tools": {name: True for name in approval},
        "pii_types": ["email", "credit_card", "ip"],
        "tool_policy": policy,
        "tool_timeout_seconds": float(config.get("tool_timeout_seconds", 30)),
        "tool_timeouts": config.get("tool_timeouts", {}) or {},
        "checkpoint_backend": config.get("checkpoint_backend", "memory"),
        "checkpoint_path": config.get("checkpoint_path", "data/runtime/agent_checkpoints.sqlite"),
    }
    return Toolbox("robot_vacuum", tools, middleware=middleware, defaults=defaults)


def _retail_expert() -> Toolbox:
    """评测/演示用：同一工具箱里放两套按 domain 过滤的 RAG 检索。

    两个 spec 场景（clothing_service / retail_router）共用这个工具箱；
    场景只通过 ``tools`` 白名单选择自己看得到的那一个。
    """
    from core.agent.middleware import log_before_model, monitor_tool
    from core.tools.rag.tools import build_rag_tools

    _, robot_retrieve = build_rag_tools(
        where={"domain": "robot"},
        summarize_name="robot_rag",
        retrieve_name="robot_retrieve",
    )
    _, clothing_retrieve = build_rag_tools(
        where={"domain": "clothing"},
        summarize_name="clothing_rag",
        retrieve_name="clothing_retrieve",
    )
    return Toolbox(
        "retail_expert",
        (robot_retrieve, clothing_retrieve),
        middleware=(monitor_tool, log_before_model),
        defaults={
            "middleware": [monitor_tool, log_before_model],
            "tool_policy": {
                "default": "allow",
                "risk_levels": {
                    "robot_retrieve": "low",
                    "clothing_retrieve": "low",
                },
            },
            "tool_timeout_seconds": 60,
            "checkpoint_backend": "memory",
        },
    )


def _research_assistant() -> Toolbox:
    from core.agent.subagent import build_subagent_tool
    from core.runtime.config import RuntimeConfig, SubagentConfig
    from core.scenarios.research_assistant.tools import SourceStore, build_research_tools

    store = SourceStore(RESEARCH_SOURCES, RESEARCH_REPORTS)
    base = build_research_tools(store)
    subagent = SubagentConfig(
        allowed_tools=["list_sources", "read_source", "search_sources"],
        max_model_calls=6,
        token_budget=12000,
        timeout_seconds=90,
        system_prompt=(
            "你是研究子 Agent。只阅读和总结资料，引用资料 id；不要改文件，不要继续委派。"
        ),
    )
    runtime = RuntimeConfig(
        workspace=RESEARCH_SOURCES,
        log_dir=RESEARCH_LOG_DIR,
        subagent=subagent,
    )
    subagent_tool = build_subagent_tool(chat_model, base, subagent, parent_runtime=runtime)
    from core.agent.middleware import log_before_model, monitor_tool

    return Toolbox(
        "research_assistant",
        tuple(base) + (subagent_tool,),
        runtime=runtime,
        middleware=(monitor_tool, log_before_model),
        defaults={
            "middleware": [monitor_tool, log_before_model],
            "tool_policy": {
                "default": "allow",
                "risk_levels": {
                    "list_sources": "low",
                    "read_source": "low",
                    "search_sources": "low",
                    "write_report": "medium",
                    "subagent": "medium",
                },
            },
            "tool_timeout_seconds": 60,
            "tool_timeouts": {"subagent": 180, "write_report": 60},
            "checkpoint_backend": "sqlite",
            "checkpoint_path": "data/runtime/research_assistant_checkpoints.sqlite",
        },
    )


def _mcp_demo() -> Toolbox:
    from core.mcp.client import load_default_tools

    return Toolbox("mcp_demo", tuple(load_default_tools()))


def _router() -> Toolbox:
    from core.agent.middleware import log_before_model, monitor_tool
    from core.scenarios.router import routes as route_table

    table = route_table.load_routes("router")
    defaults = {
        "middleware": [monitor_tool, log_before_model],
        "tool_policy": {"default": "allow", "risk_levels": route_table.risk_levels(table)},
        "tool_timeout_seconds": 180,
        "tool_timeouts": route_table.timeouts(table),
        "planning_policy": route_table.build_policy(table),
        "checkpoint_backend": "sqlite",
        "checkpoint_path": "data/runtime/spec_router_checkpoints.sqlite",
    }
    return Toolbox(
        "router",
        tuple(route_table.build_route_tools(table)),
        defaults=defaults,
    )


_BUILDERS = {
    "clothing_service": _retail_expert,
    "coding_demo": _coding_demo,
    "general": _general,
    "mcp_demo": _mcp_demo,
    "office": _office,
    "research_assistant": _research_assistant,
    "retail_expert": _retail_expert,
    "retail_router": _retail_expert,
    "robot_vacuum": _robot_vacuum,
    "router": _router,
    "structured_demo": _structured_demo,
    "workspace_assistant": _workspace_assistant,
}


@lru_cache(maxsize=None)
def toolbox(name: str | None = None) -> Toolbox:
    """按场景名取工具箱；没有专属池的场景走 office。"""
    builder = _BUILDERS.get(str(name or ""), _office)
    return builder()


def tool_names(name: str | None = None) -> list[str]:
    return [str(getattr(tool, "name", "")) for tool in toolbox(name).tools]


def clear_cache() -> None:
    """测试用：改了工具配置后重新构建。"""
    toolbox.cache_clear()
