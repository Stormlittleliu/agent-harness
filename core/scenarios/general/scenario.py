"""通用白板场景：不绑定任何业务工具，只保留 Harness 能力。

用途：
- 作为新场景的起点；
- 在控制台里对比“有业务工具”和“纯 Harness”的行为差异。
"""
from pathlib import Path

from core.agent.contracts import Scenario
from core.llm.factory import chat_model


def build_scenario() -> Scenario:
    return Scenario(
        name="general",
        description="通用白板 Agent：无业务工具，仅保留 LangChain Harness 能力",
        model=chat_model,
        system_prompt="你是一个大模型助手。",
        tools=[],
        middleware=[],
        context={},
        cases_path=Path(__file__).with_name("cases.jsonl"),
        high_risk_tools={},
        fallback_model=None,
        enable_todo=True,
        enable_summarization=True,
        summarization_trigger=("messages", 30),
        summarization_keep=("messages", 12),
        tool_call_limit=12,
        token_budget=40000,
        pii_types=[],
        checkpoint=True,
        checkpoint_backend="memory",
        checkpoint_path="data/runtime/general_checkpoints.sqlite",
        tool_policy={
            "default": "allow",
            "allow": [],
            "deny": [],
            "require_approval": [],
            "risk_levels": {},
        },
        tool_timeout_seconds=30,
        tool_timeouts={},
        workflow_factory=None,
    )
