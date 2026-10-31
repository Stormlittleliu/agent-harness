# -*- coding: utf-8 -*-
"""统一任务 schema：不同 benchmark 的样本都归一化成 BenchTask。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class BenchTask:
    id: str
    source: str
    source_version: str
    split: str
    category: str
    task_type: str
    instruction: str
    grader: str
    environment: dict
    bucket: str = "capability"  # capability / regression / adversarial / multi_turn
    initial_state: dict = field(default_factory=dict)
    tools: list[dict] = field(default_factory=list)
    policy: str = ""
    success_criteria: list[dict] = field(default_factory=list)
    reference: str = ""
    difficulty: str = "unknown"
    license: str = ""
    url: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
