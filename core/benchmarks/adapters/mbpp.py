# -*- coding: utf-8 -*-
"""MBPP 适配器：974 条 Python 函数生成，sanitized 子集另算。

和 HumanEval 一样，``grader`` 是 unit_test，执行沙箱未接；这里只归一化
题面、测试断言和 setup code，不把参考实现塞进 metadata（避免泄漏）。
"""
from __future__ import annotations

import json

from core.benchmarks.adapters.base import BenchmarkAdapter, git_version
from core.benchmarks.paths import MBPP_ROOT
from core.benchmarks.schema import BenchTask

DATA = MBPP_ROOT / "mbpp.jsonl"


class MBPPAdapter(BenchmarkAdapter):
    name = "mbpp"
    license = "Apache-2.0"
    url = "https://github.com/google-research/google-research/tree/master/mbpp"

    def available(self) -> bool:
        return DATA.is_file()

    def version(self) -> str:
        return git_version(MBPP_ROOT) if MBPP_ROOT.exists() else "unknown"

    def note(self) -> str:
        return "974 条 Python 函数生成；判分要执行单测，执行沙箱未接。"

    def load(self) -> list[BenchTask]:
        if not self.available():
            return []
        rows = []
        for line in DATA.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            task_id = item.get("task_id")
            tests = item.get("test_list") or []
            rows.append(BenchTask(
                id=f"mbpp-{task_id}",
                source=self.name,
                source_version=self.version(),
                split="test",
                category="function_generation",
                task_type="code_generation",
                instruction=str(item.get("text") or ""),
                grader="unit_test",
                bucket="capability",
                environment={
                    "kind": "mbpp",
                    "runner": "sandbox_required",
                    "timeout_seconds": 10,
                },
                success_criteria=[{
                    "type": "unit_test",
                    "tests": tests,
                    "setup": item.get("test_setup_code") or "",
                }],
                license=self.license,
                url=self.url,
                metadata={
                    "task_id": task_id,
                    "test_count": len(tests),
                    "challenge_test_count": len(item.get("challenge_test_list") or []),
                },
            ))
        return rows
