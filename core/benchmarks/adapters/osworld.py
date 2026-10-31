# -*- coding: utf-8 -*-
"""OSWorld 适配器：读取本地 evaluation_examples/*.json；执行需要 VM。"""
import json

from core.benchmarks.adapters.base import BenchmarkAdapter, git_version
from core.benchmarks.paths import OSWORLD_ROOT
from core.benchmarks.schema import BenchTask


class OSWorldAdapter(BenchmarkAdapter):
    name = "osworld"
    license = "Apache-2.0"
    url = "https://github.com/xlang-ai/OSWorld"

    def available(self) -> bool:
        return OSWORLD_ROOT.exists() and any(OSWORLD_ROOT.glob("evaluation_examples/**/*.json"))

    def version(self) -> str:
        return git_version(OSWORLD_ROOT) if OSWORLD_ROOT.exists() else "unknown"

    def note(self) -> str:
        return "桌面/OS 多步任务；需要虚拟机或 Docker 桌面环境。"

    def load(self) -> list[BenchTask]:
        if not self.available():
            return []
        rows = []
        for path in sorted(OSWORLD_ROOT.glob("evaluation_examples/**/*.json")):
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(item, dict) or "instruction" not in item:
                continue
            task_id = item.get("id", path.stem)
            category = f"os_{path.parent.name}"
            rows.append(BenchTask(
                id=f"osworld-{task_id}",
                source=self.name,
                source_version=self.version(),
                split="test",
                category=category,
                task_type="desktop",
                instruction=item.get("instruction", ""),
                grader="code",
                environment={
                    "kind": "osworld",
                    "runner": "external",
                    "snapshot": item.get("snapshot", ""),
                    "vm": True,
                },
                success_criteria=[{"type": "os_eval", "raw": item.get("evaluator", {})}],
                license=self.license,
                url=self.url,
                metadata={"task_id": task_id, "config": item.get("config")},
            ))
        return rows
