# -*- coding: utf-8 -*-
"""给 MCP 的 async 工具提供一个同步入口。

FrameworkAgent 目前是同步 invoke；MCP 工具是 async-only。这里用一个常驻
事件循环线程把 `tool.ainvoke(...)` 转成同步调用，避免每次新建/关闭 loop。
"""
from __future__ import annotations

import asyncio
import threading
from typing import Any, Coroutine


class AsyncRunner:
    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()

    def run(self, coro: Coroutine[Any, Any, Any], timeout: float = 180.0) -> Any:
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=timeout)


_RUNNER = AsyncRunner()


def run_async(coro: Coroutine[Any, Any, Any], timeout: float = 180.0) -> Any:
    return _RUNNER.run(coro, timeout=timeout)
