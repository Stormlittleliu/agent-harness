"""扫地 / 扫拖机器人客服场景：把原有业务工具、提示词和中间件封装成一个 Scenario。

业务代码仍保留在 agent/tools/ 与 config/ 下；框架层不再直接 import 它们，
只有本文件（场景层）负责组装。
"""
from pathlib import Path

from agent.tools.agent_tools import (
    fetch_external_data,
    get_current_month,
    get_user_id,
    get_user_location,
    get_weather,
    rag_summarize,
    reset_device,
)
from agent.tools.middleware import (
    intent_router,
    limit_steps,
    log_before_model,
    monitor_tool,
    report_prompt_switch,
    validate_tool_args,
)
from model.factory import chat_model
from scenarios.base import Scenario
from utils.prompt_loader import load_system_prompts


def build_scenario() -> Scenario:
    return Scenario(
        name="robot_vacuum",
        description="扫地/扫拖机器人智能客服（原项目预设业务场景）",
        model=chat_model,
        system_prompt=load_system_prompts(),
        tools=[
            rag_summarize,
            get_weather,
            get_user_location,
            get_user_id,
            get_current_month,
            fetch_external_data,
            reset_device,
        ],
        middleware=[
            monitor_tool,
            validate_tool_args,
            intent_router,
            log_before_model,
            limit_steps,
            report_prompt_switch,
        ],
        # 中间件之间通过 runtime.context 共享 intent；空字典会被 LangGraph 丢弃
        context={"intent": None},
        cases_path=Path(__file__).with_name("cases.jsonl"),
        # 框架级 Harness 能力
        high_risk_tools={"reset_device": True},
        fallback_model=None,
        enable_todo=True,
        enable_summarization=True,
        summarization_trigger=("messages", 30),
        summarization_keep=("messages", 12),
        tool_call_limit=12,
        pii_types=["email", "credit_card", "ip"],
        checkpoint=True,
    )
