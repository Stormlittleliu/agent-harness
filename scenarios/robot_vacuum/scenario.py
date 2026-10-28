"""扫地 / 扫拖机器人客服场景：把业务工具、提示词和中间件封装成一个 Scenario。

业务代码在 tools/business 与 config/ 下；框架层不直接 import 它们，
只有本文件（场景层）负责组装。
"""
from pathlib import Path

from agent.contracts import Scenario
from agent.tools.middleware import (
    LimitStepsMiddleware,
    ValidateToolArgsMiddleware,
    log_before_model,
    monitor_tool,
)
from model.factory import chat_model
from scenarios.robot_vacuum.graph import build_graphs
from scenarios.robot_vacuum.middleware import IntentRouterMiddleware, ReportPromptSwitchMiddleware
from scenarios.robot_vacuum.validators import VALIDATORS
from tools.business.tools import (
    configure_business_tools,
    fetch_external_data,
    get_current_month,
    get_user_id,
    get_user_location,
    get_weather,
    reset_device,
)
from tools.rag.tools import build_rag_tools
from utils.config_handler import load_agent_config
from utils.path_tool import get_abs_path
from utils.prompt_loader import load_system_prompts

AGENT_CONFIG_PATH = get_abs_path("scenarios/robot_vacuum/config/agent.yml")
PROMPTS_PATH = get_abs_path("scenarios/robot_vacuum/config/prompts.yml")


def build_scenario() -> Scenario:
    agent_conf = load_agent_config(AGENT_CONFIG_PATH)
    configure_business_tools(agent_conf.get("external_data_path"))
    policy = agent_conf.get("tool_policy", {}) or {}
    approval = policy.get("require_approval") or ["reset_device"]
    rag_summarize, _ = build_rag_tools()
    return Scenario(
        name="robot_vacuum",
        description="扫地/扫拖机器人智能客服（原项目预设业务场景）",
        model=chat_model,
        system_prompt=load_system_prompts(PROMPTS_PATH),
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
            ValidateToolArgsMiddleware(VALIDATORS),
            IntentRouterMiddleware(agent_conf.get("intent", {}).get("report_keywords", [])),
            log_before_model,
            LimitStepsMiddleware(int(agent_conf.get("max_model_calls", 5))),
            ReportPromptSwitchMiddleware(PROMPTS_PATH),
        ],
        # 中间件之间通过 runtime.context 共享 intent；空字典会被 LangGraph 丢弃
        context={"intent": None},
        cases_path=Path(__file__).with_name("cases.jsonl"),
        # 框架级 Harness 能力
        high_risk_tools={name: True for name in approval},
        fallback_model=None,
        enable_todo=True,
        enable_summarization=True,
        summarization_trigger=("messages", 30),
        summarization_keep=("messages", 12),
        tool_call_limit=12,
        pii_types=["email", "credit_card", "ip"],
        checkpoint=True,
        checkpoint_backend=agent_conf.get("checkpoint_backend", "memory"),
        checkpoint_path=agent_conf.get("checkpoint_path", "data/runtime/agent_checkpoints.sqlite"),
        tool_policy=policy,
        tool_timeout_seconds=float(agent_conf.get("tool_timeout_seconds", 30)),
        tool_timeouts=agent_conf.get("tool_timeouts", {}) or {},
        workflow_factory=build_graphs,
    )
