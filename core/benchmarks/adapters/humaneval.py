# -*- coding: utf-8 -*-
"""HumanEval 适配器：164 条函数补全。

``grader`` 是 unit_test；本仓库还没有代码执行沙箱，所以 runner 标记为
``sandbox_required``。适配器只负责把题面、测试和入口点归一化，不假装能跑。
"""
from __future__ import annotations

import gzip
import json

from core.benchmarks.adapters.base import BenchmarkAdapter, git_version
from core.benchmarks.paths import HUMANEVAL_ROOT
from core.benchmarks.schema import BenchTask

DATA = HUMANEVAL_ROOT / "data" / "HumanEval.jsonl.gz"


def read_gz_jsonl(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


class HumanEvalAdapter(BenchmarkAdapter):
    name = "humaneval"
    license = "MIT"
    url = "https://github.com/openai/human-eval"

    def available(self) -> bool:
        return DATA.is_file()

    def version(self) -> str:
        return git_version(HUMANEVAL_ROOT) if HUMANEVAL_ROOT.exists() else "unknown"

    def note(self) -> str:
        return "164 条 Python 函数补全；判分要执行单测，执行沙箱未接。"

    def load(self) -> list[BenchTask]:
        if not self.available():
            return []
        rows = []
        for item in read_gz_jsonl(DATA):
            task_id = str(item.get("task_id") or "")
            entry_point = str(item.get("entry_point") or "")
            rows.append(BenchTask(
                id=f"humaneval-{task_id.replace('/', '-')}",
                source=self.name,
                source_version=self.version(),
                split="test",
                category="function_completion",
                task_type="code_generation",
                instruction=str(item.get("prompt") or ""),
                grader="unit_test",
                bucket="capability",
                eval_scope="model_capability",
                environment={
                    "kind": "humaneval",
                    "runner": "sandbox_required",
                    "entry_point": entry_point,
                    "timeout_seconds": 10,
                },
                success_criteria=[{
                    "type": "unit_test",
                    "entry_point": entry_point,
                    "test": item.get("test") or "",
                }],
                license=self.license,
                url=self.url,
                metadata={"task_id": task_id},
            ))
        return rows
