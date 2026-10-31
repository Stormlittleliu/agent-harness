"""Harness 与场景之间的契约。

`agent/` 只依赖这个文件，不依赖 `scenarios/<name>/` 的任何具体实现；
场景层负责实现/组装它。这样依赖方向是：

    scenarios → agent.contracts ← agent
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Scenario:
    name: str
    description: str
    model: Any
    system_prompt: str
    tools: list[Any]
    middleware: list[Any] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    cases_path: Path | None = None
    # Harness 能力（可选）
    high_risk_tools: dict[str, Any] = field(default_factory=dict)
    fallback_model: Any = None
    enable_todo: bool = True
    enable_summarization: bool = True
    summarization_trigger: tuple = ("messages", 30)
    summarization_keep: tuple = ("messages", 12)
    tool_call_limit: int | None = 12
    token_budget: int | None = None
    pii_types: list[str] = field(default_factory=list)
    checkpoint: bool = True
    checkpoint_backend: str = "memory"
    checkpoint_path: str = "data/runtime/agent_checkpoints.sqlite"
    # 工具权限与超时
    tool_policy: dict[str, Any] = field(default_factory=dict)
    tool_timeout_seconds: float = 30.0
    tool_timeouts: dict[str, float] = field(default_factory=dict)
    # 场景自己的 LangGraph 工厂：WorkflowRuntime 调用它获取 compiled graph
    workflow_factory: Any = None
    # 可选运行时：hooks / 工作区 / 任务库，由 core.runtime.RuntimeConfig 提供
    runtime: Any = None

    def get_tool(self, name: str):
        """按名字取场景注册的工具；能力层评测/调试用。"""
        for tool in self.tools:
            if getattr(tool, "name", None) == name:
                return tool
        raise KeyError(f"场景 {self.name} 没有注册工具：{name}")
