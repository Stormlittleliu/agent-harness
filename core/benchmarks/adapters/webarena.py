# -*- coding: utf-8 -*-
"""WebArena 适配器：读取本地 config_files/*.json；执行需要自托管网站。"""
import json

from core.benchmarks.adapters.base import BenchmarkAdapter, git_version
from core.benchmarks.paths import WEBARENA_ROOT
from core.benchmarks.schema import BenchTask


class WebArenaAdapter(BenchmarkAdapter):
    name = "webarena"
    license = "Apache-2.0"
    url = "https://github.com/web-arena-x/webarena"

    def available(self) -> bool:
        return WEBARENA_ROOT.exists() and any(WEBARENA_ROOT.glob("config_files/*.json"))

    def version(self) -> str:
        return git_version(WEBARENA_ROOT) if WEBARENA_ROOT.exists() else "unknown"

    def note(self) -> str:
        return "Web 多步任务；需要 Docker 自托管 shopping/reddit/gitlab 等网站。"

    def load(self) -> list[BenchTask]:
        if not self.available():
            return []
        rows = []
        for path in sorted(WEBARENA_ROOT.glob("config_files/*.json")):
            item = json.loads(path.read_text(encoding="utf-8"))
            task_id = item.get("task_id", path.stem)
            evaluation = item.get("eval") or {}
            rows.append(BenchTask(
                id=f"webarena-{task_id}",
                source=self.name,
                source_version=self.version(),
                split="test",
                category="web",
                task_type="web_navigation",
                instruction=item.get("intent", ""),
                grader="code",
                environment={
                    "kind": "webarena",
                    "runner": "external",
                    "start_url": item.get("start_url", ""),
                    "sites": item.get("sites", []),
                    "docker": True,
                },
                success_criteria=[{"type": "web_eval", "raw": evaluation}],
                license=self.license,
                url=self.url,
                metadata={"task_id": task_id},
            ))
        return rows
