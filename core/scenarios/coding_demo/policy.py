# -*- coding: utf-8 -*-
"""coding_demo 的委派策略（仅用于触发率实验，不改变默认场景行为）。

- 多文件对比 / 分组 / 关系类任务 -> subagent（只读、隔离上下文）；
- 明确的多步骤 / 依赖任务 -> create_task；
- 简单文件检查不委派（abstain）。
"""
from core.agent.middleware import PlanningPolicy, PlanningRule

CODING_DELEGATION_POLICY = PlanningPolicy(
    rules=(
        PlanningRule(
            tool="subagent",
            strong_keywords=("对比", "比较", "分别", "并行", "分组", "关系", "多文件"),
            keywords=("阅读", "检查"),
            priority=20,
            arg_name="description",
            arg_prefix="完成这个子任务并只返回结论：",
        ),
        PlanningRule(
            tool="create_task",
            strong_keywords=("任务", "多步骤", "依赖"),
            keywords=("先", "再", "然后"),
            priority=10,
            arg_name="subject",
            max_arg_chars=80,
        ),
    ),
    min_score=2,
    abstain_on_tie=True,
)
