# -*- coding: utf-8 -*-
"""Checkpointer 工厂：内存 / SQLite 持久化。

- memory：进程内记忆，重启即丢，适合测试；
- sqlite：写入本地文件，跨进程/重启保留会话，适合演示和单机部署。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

ROOT = Path(__file__).resolve().parents[2]


def build_checkpointer(backend: str = "memory", path: str = "data/runtime/agent_checkpoints.sqlite"):
    backend = (backend or "memory").lower()
    if backend == "sqlite":
        from langgraph.checkpoint.sqlite import SqliteSaver

        db_path = Path(path)
        if not db_path.is_absolute():
            db_path = ROOT / db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=10)
        return SqliteSaver(conn)
    if backend != "memory":
        raise ValueError(f"未知 checkpoint_backend：{backend}（可选：memory / sqlite）")
    return InMemorySaver()
