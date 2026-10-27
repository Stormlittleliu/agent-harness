"""Agent 自定义中间件。

六个中间件各司其职：
1. monitor_tool      —— 工具调用日志（每次调用/拦截都留痕）
2. validate_tool_args —— 参数校验，非法调用不执行工具，返回 error ToolMessage 让模型重新规划
3. intent_router     —— 规则关键词意图识别，结果写入 runtime.context 并记录切换日志
4. limit_steps       —— 最大模型调用步数限制，超限注入中文兜底回复并结束
5. log_before_model  —— 每次模型调用前的状态日志
6. report_prompt_switch —— 按意图动态切换系统提示词

关键机制（LangChain 1.x）：
- `wrap_tool_call` 中不调用 handler、直接返回 `ToolMessage(status="error")`，
  这条错误观察会回到模型，模型据此修正参数并重新发起调用。
- `before_agent` 只在一次 run 开始时执行一次；`wrap_model_call` 在每次模型调用前执行。
- `runtime.context` 是同一 run 内共享的可变字典，用来在中间件之间传递意图。

为什么用 AgentMiddleware 子类而不是装饰器：
`@wrap_tool_call` / `@before_agent` 等装饰器只会给函数生成同步**或**异步其中一种实现。
项目里的 `execute_stream()` 走同步链路，而 `examples/demo_agent_interfaces.py --demo events`
的 `astream_events()` 走异步链路；只写同步钩子会在异步调用工具时抛出
NotImplementedError。因此这里用类同时实现同步和异步两套钩子。
"""
import re
from typing import Any, Callable

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware, ModelRequest
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command

from agent.tools.agent_tools import month_arr, user_ids
from utils.config_handler import agent_conf
from utils.logger_handler import get_logger, logger
from utils.prompt_loader import load_report_prompts, load_system_prompts

# 意图路由独立日志：logs/intent_router_YYYYMMDD.log，供 badcase 复盘
intent_logger = get_logger("intent_router")


# ===================== 通用小工具 =====================
def _message_text(message) -> str:
    """从消息对象/字典中提取纯文本，兼容 content 为字符串或内容块列表。"""
    if isinstance(message, dict):
        content = message.get("content", "")
    else:
        content = getattr(message, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "\n".join(parts)
    return str(content or "")


def _tool_call_args(request: ToolCallRequest) -> dict:
    """取出工具调用参数；缺失或类型异常时统一返回空字典。"""
    args = request.tool_call.get("args")
    return args if isinstance(args, dict) else {}


class _MiddlewareBase(AgentMiddleware):
    """项目中间件的公共基类：统一声明不额外注册工具。"""

    tools = []


# ===================== 1. 工具调用日志 =====================
class MonitorToolMiddleware(_MiddlewareBase):
    name = "monitor_tool"

    @staticmethod
    def _log_start(request: ToolCallRequest) -> str:
        tool_name = request.tool_call["name"]
        logger.info(f"[tool monitor]执行工具：{tool_name}")
        logger.info(f"[tool monitor]传入参数：{request.tool_call.get('args')}")
        return tool_name

    @staticmethod
    def _log_result(tool_name: str, result) -> None:
        if getattr(result, "status", None) == "error":
            logger.warning(f"[tool monitor]工具{tool_name}被拦截或执行失败：{getattr(result, 'content', '')}")
        else:
            logger.info(f"[tool monitor]工具{tool_name}调用成功")

    def wrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        tool_name = self._log_start(request)
        try:
            result = handler(request)
            self._log_result(tool_name, result)
            return result
        except Exception as e:
            logger.error(f"[tool monitor]工具{tool_name}调用失败，原因：{str(e)}", exc_info=True)
            raise e

    async def awrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], Any],
    ) -> ToolMessage | Command:
        tool_name = self._log_start(request)
        try:
            result = await handler(request)
            self._log_result(tool_name, result)
            return result
        except Exception as e:
            logger.error(f"[tool monitor]工具{tool_name}调用失败，原因：{str(e)}", exc_info=True)
            raise e


# ===================== 2. 工具参数校验 =====================
def _validate_rag_summarize(args: dict) -> str | None:
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        return 'query 必须是非空字符串，例如 "扫地机器人回充失败怎么办"'
    return None


def _validate_get_weather(args: dict) -> str | None:
    city = args.get("city")
    if not isinstance(city, str) or not city.strip():
        return 'city 必须是非空字符串，例如 "深圳"'
    if len(city.strip()) > 20:
        return "city 长度不能超过 20 个字符"
    return None


def _validate_fetch_external_data(args: dict) -> str | None:
    user_id = args.get("user_id")
    month = args.get("month")

    if user_id is None:
        return '缺少 user_id 参数，必须传入纯数字字符串，例如 "1001"'
    user_id = str(user_id).strip()
    if not user_id.isdigit():
        return f'user_id 必须是纯数字字符串，收到的是 "{user_id}"，例如 "1001"'
    if user_id not in user_ids:
        return f'user_id "{user_id}" 不在可查询范围内（1001~1010），请先调用 get_user_id 获取'

    if month is None:
        return '缺少 month 参数，必须传入 YYYY-MM 格式的字符串，例如 "2025-06"'
    month = str(month).strip()
    if not re.fullmatch(r"\d{4}-\d{2}", month):
        return f'month 必须严格遵循 YYYY-MM 格式，收到的是 "{month}"，例如 "2025-06"'
    if month not in month_arr:
        return f'month "{month}" 不在可查询范围内（2025-01~2025-12），请先调用 get_current_month 获取'
    return None


def _validate_no_args(args: dict) -> str | None:
    if args:
        return "该工具不接受任何参数，请直接调用（不要传入参数）"
    return None


def _validate_reset_device(args: dict) -> str | None:
    device_id = args.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        return 'device_id 必须是非空字符串，例如 "R-1001"'
    return None


# 工具名 -> 校验函数；未列入的工具不做参数校验
VALIDATORS: dict[str, Callable[[dict], str | None]] = {
    "rag_summarize": _validate_rag_summarize,
    "get_weather": _validate_get_weather,
    "get_user_location": _validate_no_args,
    "get_user_id": _validate_no_args,
    "get_current_month": _validate_no_args,
    "fetch_external_data": _validate_fetch_external_data,
    "reset_device": _validate_reset_device,
}


def _validation_error(request: ToolCallRequest) -> ToolMessage | None:
    """返回非法参数对应的 error ToolMessage；参数合法时返回 None。"""
    tool_name = request.tool_call["name"]
    validator = VALIDATORS.get(tool_name)
    if validator is None:
        return None

    error_reason = validator(_tool_call_args(request))
    if error_reason is None:
        return None

    logger.warning(f"[参数校验失败]工具 {tool_name}：{error_reason}")
    return ToolMessage(
        content=(
            f"[参数校验失败] 工具 {tool_name} 的调用参数不合法：{error_reason}。"
            "请修正参数后重新调用该工具。"
        ),
        tool_call_id=request.tool_call.get("id", ""),
        name=tool_name,
        status="error",
    )


class ValidateToolArgsMiddleware(_MiddlewareBase):
    """拦截非法工具参数，把错误作为 Observation 重新注入 Agent 循环。

    不调用 handler，直接返回 status="error" 的 ToolMessage：
    模型看到错误原因后可以修正参数、重新规划；整个 run 不会因为一次非法调用而中断。
    """

    name = "validate_tool_args"

    def wrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        error = _validation_error(request)
        if error is not None:
            return error
        return handler(request)

    async def awrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], Any],
    ) -> ToolMessage | Command:
        error = _validation_error(request)
        if error is not None:
            return error
        return await handler(request)


# ===================== 3. 意图路由 =====================
def _classify_intent(text: str) -> tuple[str, str]:
    """规则关键词分类：命中报告类关键词 -> report，否则 -> qa。"""
    keywords = agent_conf.get("intent", {}).get("report_keywords", [])
    lowered = text.lower()
    for keyword in keywords:
        keyword = str(keyword).strip()
        if keyword and keyword.lower() in lowered:
            return "report", keyword
    return "qa", ""


def _route_intent(state: AgentState, runtime: Runtime):
    """一次 run 开始时识别用户意图，并写入 runtime.context 供提示词切换使用。"""
    context = runtime.context
    if not isinstance(context, dict):
        logger.warning(
            f"[intent_router]runtime.context 不是字典（收到 {type(context).__name__}），无法写入意图标记；"
            "请给 stream/invoke 传入非空 context，例如 {'intent': None}"
        )
        return None
    if context.get("intent") is not None:
        return None

    messages = state.get("messages", [])
    question = ""
    for message in reversed(messages):
        is_human = isinstance(message, HumanMessage) or (
            isinstance(message, dict) and message.get("role") == "user"
        )
        if is_human:
            question = _message_text(message).strip()
            break

    intent, matched_keyword = _classify_intent(question)
    context["intent"] = intent
    context["intent_keyword"] = matched_keyword

    # 切换日志：时间 / 问题 / 意图 / 命中关键词，复盘 badcase 时直接检索该文件
    intent_logger.info(
        f"question={question!r} | intent={intent} | matched_keyword={matched_keyword!r}"
    )
    return None


class IntentRouterMiddleware(_MiddlewareBase):
    name = "intent_router"

    def before_agent(self, state: AgentState, runtime: Runtime):
        return _route_intent(state, runtime)

    async def abefore_agent(self, state: AgentState, runtime: Runtime):
        return _route_intent(state, runtime)


# ===================== 4. 最大步数限制 =====================
def _limit_steps(state: AgentState, runtime: Runtime):
    """模型调用次数达到上限时，直接结束并返回中文兜底回复。"""
    max_model_calls = int(agent_conf.get("max_model_calls", 5))
    model_calls = sum(1 for message in state.get("messages", []) if isinstance(message, AIMessage))

    if model_calls < max_model_calls:
        return None

    logger.warning(f"[limit_steps]模型调用已达上限 {max_model_calls} 次，结束本次 run")
    return {
        "jump_to": "end",
        "messages": [
            AIMessage(
                content=(
                    f"抱歉，该问题的处理步骤已超过上限（{max_model_calls} 步），"
                    "我暂时无法给出可靠回答。请补充更具体的信息后重试。"
                )
            )
        ],
    }


class LimitStepsMiddleware(_MiddlewareBase):
    name = "limit_steps"

    def before_model(self, state: AgentState, runtime: Runtime):
        return _limit_steps(state, runtime)

    async def abefore_model(self, state: AgentState, runtime: Runtime):
        return _limit_steps(state, runtime)


# `can_jump_to` 由 Agent 工厂从钩子方法上读取，同步/异步方法都要标记
LimitStepsMiddleware.before_model.__can_jump_to__ = ["end"]
LimitStepsMiddleware.abefore_model.__can_jump_to__ = ["end"]


# ===================== 5. 模型调用日志 =====================
def _log_before_model(state: AgentState) -> None:
    messages = state.get("messages", [])
    logger.info(f"[log_before_model]即将调用模型，带有{len(messages)}条消息。")
    if messages:
        last_message = messages[-1]
        logger.debug(
            f"[log_before_model]{type(last_message).__name__} | "
            f"{_message_text(last_message).strip()}"
        )
    return None


class LogBeforeModelMiddleware(_MiddlewareBase):
    name = "log_before_model"

    def before_model(self, state: AgentState, runtime: Runtime):
        return _log_before_model(state)

    async def abefore_model(self, state: AgentState, runtime: Runtime):
        return _log_before_model(state)


# ===================== 6. 提示词切换 =====================
def _select_prompt(request: ModelRequest) -> str:
    """按意图路由的结果选择系统提示词。"""
    intent = request.runtime.context.get("intent", "qa") if isinstance(request.runtime.context, dict) else "qa"
    if intent == "report":
        return load_report_prompts()
    return load_system_prompts()


class ReportPromptSwitchMiddleware(_MiddlewareBase):
    """按意图路由的结果，在每次模型调用前替换 system prompt。"""

    name = "report_prompt_switch"

    @staticmethod
    def _with_prompt(request: ModelRequest) -> ModelRequest:
        return request.override(system_message=SystemMessage(content=_select_prompt(request)))

    def wrap_model_call(self, request: ModelRequest, handler):
        return handler(self._with_prompt(request))

    async def awrap_model_call(self, request: ModelRequest, handler):
        return await handler(self._with_prompt(request))


# 统一导出中间件实例，调用方（ReactAgent / demo）的导入方式不变
monitor_tool = MonitorToolMiddleware()
validate_tool_args = ValidateToolArgsMiddleware()
intent_router = IntentRouterMiddleware()
limit_steps = LimitStepsMiddleware()
log_before_model = LogBeforeModelMiddleware()
report_prompt_switch = ReportPromptSwitchMiddleware()
