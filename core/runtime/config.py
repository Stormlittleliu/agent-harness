# -*- coding: utf-8 -*-
"""场景层运行时配置：hooks / 工作区 / 任务库。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable


@dataclass
class RuntimeConfig:
    workspace: Path | None = None
    task_store_path: Path | None = None
    log_dir: Path | None = None
    hooks: dict[str, list[Callable]] = field(default_factory=dict)
    # 由场景构建时注入，供 GUI / TaskRunner 复用
    task_store: Any = None
