# -*- coding: utf-8 -*-
"""场景层运行时配置：hooks / 工作区 / 任务库。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class SubagentConfig:
    name: str = "subagent"
    description: str = (
        "派生一个子 Agent 处理自包含的子任务；子 Agent 使用全新上下文，"
        "只返回最终结论，不返回中间过程。"
    )
    system_prompt: str = (
        "你是一个子 Agent。专注完成被委派的任务，完成后返回简洁结论；"
        "不要继续委派。"
    )
    allowed_tools: list[str] = field(default_factory=list)
    max_model_calls: int = 20
    token_budget: int = 20000
    timeout_seconds: float = 120.0


@dataclass
class RuntimeConfig:
    workspace: Path | None = None
    task_store_path: Path | None = None
    log_dir: Path | None = None
    hooks: dict[str, list[Callable]] = field(default_factory=dict)
    # 由场景构建时注入，供 GUI / TaskRunner 复用
    task_store: Any = None
    subagent: SubagentConfig | None = None
