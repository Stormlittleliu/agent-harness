"""业务场景接口：Agent 框架只依赖这个抽象，不依赖任何具体业务。

一个 Scenario 负责提供：
- 模型
- 系统提示词
- 工具列表
- 中间件
- 运行上下文（例如中间件之间共享的 intent 字段）
- 该场景的测试用例文件

框架层（agent/framework.py）只认 Scenario，不 import 任何业务工具。
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
    # 框架级 Harness 能力（可选）
    high_risk_tools: dict[str, Any] = field(default_factory=dict)
    fallback_model: Any = None
    enable_todo: bool = True
    enable_summarization: bool = True
    summarization_trigger: tuple = ("messages", 30)
    summarization_keep: tuple = ("messages", 12)
    tool_call_limit: int | None = 12
    pii_types: list[str] = field(default_factory=list)
    checkpoint: bool = True
