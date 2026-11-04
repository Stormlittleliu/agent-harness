# -*- coding: utf-8 -*-
"""控制台：对话 / 构建 / 质量三个产品。

- ``shell``：页面骨架、产品切换、路由分发；
- ``routes``：URL（query 参数）× 环境变量的路由解析与跳转；
- ``chat``：对话端（已发布入口 + 多轮会话 + 每轮调用链）；
- ``build``：构建端（场景库 → 场景详情 → 发布）；
- ``quality``：质量端（评测 / 复核 / 优化 / 自检 / 数据集 / 基准 / 成本 / 记录）。

原来的 ``core.interfaces.agent_dashboard`` 只保留兼容入口，页面骨架搬到这里。
"""
from core.interfaces.console.shell import run

__all__ = ["run"]
