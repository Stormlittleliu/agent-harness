# -*- coding: utf-8 -*-
"""单次 run 的 token 预算。

trace callback 在所有模型调用（含 RAG 工具内部的总结调用）结束后累加；
TokenBudgetMiddleware 在每次模型调用前检查，超限就结束 run。
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class RunBudget:
    max_tokens: int | None = None
    total_tokens: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def add(self, tokens: int) -> None:
        if tokens <= 0:
            return
        with self._lock:
            self.total_tokens += int(tokens)

    @property
    def exceeded(self) -> bool:
        return bool(self.max_tokens and self.total_tokens >= self.max_tokens)

    @property
    def remaining(self) -> int | None:
        if not self.max_tokens:
            return None
        return max(self.max_tokens - self.total_tokens, 0)
