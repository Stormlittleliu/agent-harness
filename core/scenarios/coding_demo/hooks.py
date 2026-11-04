# -*- coding: utf-8 -*-
"""编码场景的运行时钩子：日志 + 危险命令 / 越界写入的兜底拦截。

放在独立模块是为了让"代码场景"和它的 spec 仿造版共用同一套钩子——
钩子不写进 spec（spec 只能声明，不能描述代码），但两边行为要一致。
"""
from __future__ import annotations

from pathlib import Path

from core.runtime.workspace import DENY_COMMANDS, DENY_WRITE_PARTS
from core.utils.logger_handler import logger


def prompt_hook(query: str):
    logger.info(f"[hook:UserPromptSubmit] {query[:80]}")
    return None


def pre_tool_hook(request):
    tool_call = request.tool_call or {}
    name = tool_call.get("name", "")
    args = tool_call.get("args") or {}
    logger.info(f"[hook:PreToolUse] {name} {str(args)[:120]}")
    if name == "run_command":
        command = str(args.get("command", "")).lower()
        for pattern in DENY_COMMANDS:
            if pattern in command:
                return f"命令被 hook 拦截：包含危险模式 {pattern!r}"
    if name in {"write_file", "edit_file"}:
        raw_path = str(args.get("path", "")).replace("\\", "/")
        parts = [part for part in raw_path.split("/") if part]
        if Path(raw_path).is_absolute() or ".." in parts:
            return f"写入路径必须是工作区内的相对路径：{raw_path}"
        for part in DENY_WRITE_PARTS:
            if part in parts:
                return f"禁止写入受保护目录：{part}"
    return None


def post_tool_hook(request, result):
    text = str(result)
    if len(text) > 5000:
        logger.warning(f"[hook:PostToolUse] 输出较大：{len(text)} chars")
    return None


def stop_hook(messages):
    logger.info(f"[hook:Stop] messages={len(messages or [])}")
    return None


def task_start_hook(task):
    logger.info(f"[hook:TaskStart] {task.id} {task.subject}")


def task_complete_hook(task, answer, unblocked):
    logger.info(f"[hook:TaskComplete] {task.id} unblocked={[item.id for item in unblocked]}")


def task_fail_hook(task, error):
    logger.warning(f"[hook:TaskFail] {task.id} {error}")


def hooks() -> dict:
    """RuntimeConfig.hooks 的完整映射。"""
    return {
        "UserPromptSubmit": [prompt_hook],
        "PreToolUse": [pre_tool_hook],
        "PostToolUse": [post_tool_hook],
        "Stop": [stop_hook],
        "TaskStart": [task_start_hook],
        "TaskComplete": [task_complete_hook],
        "TaskFail": [task_fail_hook],
    }
