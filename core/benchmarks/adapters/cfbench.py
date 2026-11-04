# -*- coding: utf-8 -*-
"""CFBench 适配器：中文多约束遵循，1000 条单轮任务。

上游字段 ``doamin`` 是拼写错误，原样保留，不做改写。
判分依赖 LLM judge（约束是否满足），不是执行环境；所以 runner 是 native。
"""
from __future__ import annotations

import json

from core.benchmarks.adapters.base import BenchmarkAdapter, git_version
from core.benchmarks.paths import CFBENCH_ROOT
from core.benchmarks.schema import BenchTask

DATA = CFBENCH_ROOT / "data" / "cfbench_data.json"


def answerability(value: str) -> str:
    """把上游的 是/否 归一成可读标签；空值保留为 unknown。"""
    if value == "是":
        return "answerable"
    if value == "否":
        return "unanswerable"
    return "unknown"


class CFBenchAdapter(BenchmarkAdapter):
    name = "cfbench"
    license = "未附 LICENSE（上游仓库）"
    url = "https://github.com/PKU-Baichuan-MLSystemLab/CFBench"

    def available(self) -> bool:
        return DATA.is_file()

    def version(self) -> str:
        return git_version(CFBENCH_ROOT) if CFBENCH_ROOT.exists() else "unknown"

    def note(self) -> str:
        return "中文多约束遵循；1000 条，约束满足靠 LLM judge，不是执行环境。"

    def load(self) -> list[BenchTask]:
        if not self.available():
            return []
        raw = json.loads(DATA.read_text(encoding="utf-8"))
        rows = []
        for item in raw:
            split = str(item.get("split") or "unknown")
            answerable = answerability(str(item.get("isanswer") or ""))
            criteria = item.get("criteria") or []
            checks = []
            for criterion in criteria:
                if not isinstance(criterion, (list, tuple)) or not criterion:
                    continue
                checks.append({
                    "type": "constraint",
                    "value": criterion[0],
                    "priority": criterion[1] if len(criterion) > 1 else "",
                    "kind": criterion[2] if len(criterion) > 2 else "",
                    "family": criterion[3] if len(criterion) > 3 else "",
                })
            if answerable == "answerable" and item.get("gold") not in (None, ""):
                checks.append({"type": "answer", "value": item.get("gold")})
            rows.append(BenchTask(
                id=f"cfbench-{item.get('idx')}",
                source=self.name,
                source_version=self.version(),
                split=split,
                category=f"{split}_{answerable}",
                task_type="constraint_following",
                instruction=str(item.get("prompt") or ""),
                grader="mixed",
                bucket="adversarial" if answerable == "unanswerable" else "capability",
                environment={"kind": "cfbench", "runner": "native", "judge": "llm"},
                success_criteria=checks,
                difficulty=split,
                license=self.license,
                url=self.url,
                metadata={
                    "idx": item.get("idx"),
                    "domain": item.get("doamin"),
                    "scenario": item.get("scenario"),
                    "source": item.get("source"),
                    "answerable": answerable,
                    "criteria_count": len(criteria),
                },
            ))
        return rows
