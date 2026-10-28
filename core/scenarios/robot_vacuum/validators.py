# -*- coding: utf-8 -*-
"""robot_vacuum 场景的工具参数校验规则。

放在场景层，避免 agent/（Harness）依赖具体业务常量。
"""
import re
from typing import Callable

from core.tools.business.constants import month_arr, user_ids


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
