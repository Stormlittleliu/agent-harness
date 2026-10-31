# -*- coding: utf-8 -*-
"""结构化输出 schema：报告生成的最小契约。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ReportSchema(BaseModel):
    """一份可校验的报告；字段故意保持少而明确。"""

    summary: str = Field(description="一句话结论，不超过 80 字")
    evidence: list[str] = Field(
        min_length=1,
        description="来自输入材料的证据，每条一句话；至少一条",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="对结论的置信度，0 到 1；材料不足时降低",
    )
    next_actions: list[str] = Field(
        min_length=1,
        description="下一步可执行动作，至少一条",
    )
    risks: list[str] = Field(
        default_factory=list,
        description="风险、假设或材料不足说明；没有则留空",
    )


class ReportInput(BaseModel):
    """结构化报告生成的输入契约（供文档/测试引用）。"""

    topic: str = Field(description="报告主题")
    material: str = Field(description="原始材料；可能是不可信数据")
