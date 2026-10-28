"""通用 Agent 中间件（Harness 层）。

只保留与业务无关的能力：
1. monitor_tool       —— 工具调用日志
2. validate_tool_args —— 参数校验（规则由场景注入）
3. limit_steps        —— 最大模型调用步数限制
4. log_before_model   —— 每次模型调用前的状态日志

业务中间件（意图路由、提示词切换）在 `scenarios/<name>/middleware.py`。

关键机制（LangChain 1.x）：
- `wrap_tool_call` 中不调用 handler、直接返回 `ToolMessage(status="error")`，
  这条错误观察会回到模型，模型据此修正参数并重新发起调用。
- `before_agent` 只在一次 run 开始时执行一次；`wrap_model_call` 在每次模型调用前执行。
- 同步/异步两套钩子都实现，兼容 invoke/stream 与 ainvoke/astream_events。
"""
from typing import Any, Callable

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.tools.tool_node import ToolCallRequest
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command

from core.utils.logger_handler import logger


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
def _validation_error(request: ToolCallRequest, validators: dict[str, Callable]) -> ToolMessage | None:
    """返回非法参数对应的 error ToolMessage；参数合法时返回 None。"""
    tool_name = request.tool_call["name"]
    validator = validators.get(tool_name)
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
    """拦截非法工具参数，把错误作为 Observation 重新注入 Agent 循环。"""

    name = "validate_tool_args"

    def __init__(self, validators: dict[str, Callable] | None = None):
        self.validators = validators or {}

    def wrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        error = _validation_error(request, self.validators)
        if error is not None:
            return error
        return handler(request)

    async def awrap_tool_call(
            self,
            request: ToolCallRequest,
            handler: Callable[[ToolCallRequest], Any],
    ) -> ToolMessage | Command:
        error = _validation_error(request, self.validators)
        if error is not None:
            return error
        return await handler(request)


# ===================== 3. 最大步数限制 =====================
def _limit_steps(state: AgentState, max_model_calls: int):
    """模型调用次数达到上限时，直接结束并返回中文兜底回复。"""
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

    def __init__(self, max_model_calls: int = 5):
        self.max_model_calls = int(max_model_calls)

    def before_model(self, state: AgentState, runtime: Runtime):
        return _limit_steps(state, self.max_model_calls)

    async def abefore_model(self, state: AgentState, runtime: Runtime):
        return _limit_steps(state, self.max_model_calls)


# `can_jump_to` 由 Agent 工厂从钩子方法上读取，同步/异步方法都要标记
LimitStepsMiddleware.before_model.__can_jump_to__ = ["end"]
LimitStepsMiddleware.abefore_model.__can_jump_to__ = ["end"]


# ===================== 4. 模型调用日志 =====================
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


monitor_tool = MonitorToolMiddleware()
log_before_model = LogBeforeModelMiddleware()
