# -*- coding: utf-8 -*-
"""文件持久化的任务图：状态、owner、blocked_by、依赖解锁。

SQLite 单文件，跨进程/重启保留；适合单机 Harness 的任务编排。
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class Task:
    id: str
    subject: str
    description: str = ""
    status: str = "pending"  # pending | in_progress | completed | failed
    owner: str | None = None
    blocked_by: list[str] = field(default_factory=list)
    result: str = ""
    error: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class TaskStore:
    def __init__(self, path: Path | str):
        self.path = Path(path) if path != ":memory:" else path
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    status TEXT NOT NULL,
                    owner TEXT,
                    blocked_by TEXT DEFAULT '[]',
                    result TEXT DEFAULT '',
                    error TEXT DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}'
                )
                """
            )

    def _row(self, row: sqlite3.Row) -> Task:
        data = dict(row)
        data["blocked_by"] = json.loads(data.get("blocked_by") or "[]")
        data["metadata"] = json.loads(data.get("metadata") or "{}")
        return Task(**data)

    def create(
        self,
        subject: str,
        description: str = "",
        blocked_by: list[str] | None = None,
        metadata: dict | None = None,
    ) -> Task:
        now = _now()
        task = Task(
            id=f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:4]}",
            subject=subject,
            description=description,
            status="pending",
            blocked_by=list(blocked_by or []),
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO tasks (id, subject, description, status, owner, blocked_by, "
                "result, error, created_at, updated_at, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    task.id, task.subject, task.description, task.status, task.owner,
                    json.dumps(task.blocked_by, ensure_ascii=False), task.result, task.error,
                    task.created_at, task.updated_at,
                    json.dumps(task.metadata, ensure_ascii=False),
                ),
            )
        return task

    def get(self, task_id: str) -> Task:
        with self._lock:
            row = self._conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(f"任务不存在：{task_id}")
        return self._row(row)

    def list(self, status: str | None = None) -> list[Task]:
        sql = "SELECT * FROM tasks"
        params: tuple = ()
        if status:
            sql += " WHERE status = ?"
            params = (status,)
        sql += " ORDER BY created_at, id"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row(row) for row in rows]

    def deps_done(self, task: Task) -> bool:
        for dep_id in task.blocked_by:
            try:
                dep = self.get(dep_id)
            except KeyError:
                return False
            if dep.status != "completed":
                return False
        return True

    def ready(self) -> list[Task]:
        return [task for task in self.list("pending") if self.deps_done(task)]

    def claim(self, task_id: str, owner: str = "agent") -> Task:
        with self._lock:
            task = self.get(task_id)
            if task.status != "pending":
                raise ValueError(f"任务 {task_id} 状态为 {task.status}，不能认领")
            if not self.deps_done(task):
                waiting = [dep for dep in task.blocked_by if self._dep_incomplete(dep)]
                raise ValueError(f"任务被依赖阻塞：{waiting}")
            task.status = "in_progress"
            task.owner = owner
            task.updated_at = _now()
            with self._conn:
                self._conn.execute(
                    "UPDATE tasks SET status = ?, owner = ?, updated_at = ? WHERE id = ?",
                    (task.status, task.owner, task.updated_at, task.id),
                )
        return task

    def _dep_incomplete(self, dep_id: str) -> bool:
        try:
            return self.get(dep_id).status != "completed"
        except KeyError:
            return True

    def complete(self, task_id: str, result: str = "") -> list[Task]:
        with self._lock:
            task = self.get(task_id)
            if task.status != "in_progress":
                raise ValueError(f"任务 {task_id} 状态为 {task.status}，不能完成")
            task.status = "completed"
            task.result = result
            task.updated_at = _now()
            with self._conn:
                self._conn.execute(
                    "UPDATE tasks SET status = ?, result = ?, updated_at = ? WHERE id = ?",
                    (task.status, task.result, task.updated_at, task.id),
                )
            unblocked = [candidate for candidate in self.list("pending") if self.deps_done(candidate)]
        return unblocked

    def fail(self, task_id: str, error: str) -> Task:
        with self._lock:
            task = self.get(task_id)
            task.status = "failed"
            task.error = error
            task.updated_at = _now()
            with self._conn:
                self._conn.execute(
                    "UPDATE tasks SET status = ?, error = ?, updated_at = ? WHERE id = ?",
                    (task.status, task.error, task.updated_at, task.id),
                )
        return task

    def stats(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for task in self.list():
            counts[task.status] = counts.get(task.status, 0) + 1
        return counts

    def close(self) -> None:
        self._conn.close()


def task_to_dict(task: Task) -> dict:
    return asdict(task)
