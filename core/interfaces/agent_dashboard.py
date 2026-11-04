# -*- coding: utf-8 -*-
"""兼容入口：控制台已迁到 ``core.interfaces.console``。

保留这个模块，是为了让旧的 ``from core.interfaces.agent_dashboard import run``
（以及脚本 / 文档里的引用）不至于直接断掉。页面骨架、路由与三个产品都在
``core.interfaces.console``；这里不再保留旧的平级导航实现。
"""
from core.interfaces.console import run

__all__ = ["run"]
