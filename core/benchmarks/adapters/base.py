# -*- coding: utf-8 -*-
"""适配器基类：把各 benchmark 的原始任务归一化成 BenchTask。"""
from __future__ import annotations

import subprocess
from pathlib import Path

from core.benchmarks.schema import BenchTask


def git_version(path: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


class BenchmarkAdapter:
    name = ""
    license = ""
    url = ""

    def available(self) -> bool:
        return False

    def version(self) -> str:
        return "unknown"

    def load(self) -> list[BenchTask]:
        return []

    def note(self) -> str:
        return ""
