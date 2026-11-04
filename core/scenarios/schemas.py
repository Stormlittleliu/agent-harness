# -*- coding: utf-8 -*-
"""结构化输出 schema 注册表：spec 里只写名字，不写代码。

spec 是数据，不能内联 Pydantic 类；所以把"能给 create_agent 当 response_format
的模型"登记在这里，spec 通过 ``response_format: "ReportSchema"`` 引用。
"""
from __future__ import annotations

from typing import Any

from core.scenarios.structured_demo.schema import ReportSchema

SCHEMAS: dict[str, Any] = {
    "ReportSchema": ReportSchema,
}


def names() -> list[str]:
    return sorted(SCHEMAS)


def resolve(name: str | None) -> Any:
    """按名字取 schema；没有就返回 None（当成"不用结构化输出"）。"""
    if not name:
        return None
    return SCHEMAS.get(str(name))
