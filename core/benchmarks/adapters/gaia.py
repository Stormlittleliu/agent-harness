# -*- coding: utf-8 -*-
"""GAIA 适配器：读取本地已下载的数据；未下载时给出提示。"""
import json
from pathlib import Path

from core.benchmarks.adapters.base import BenchmarkAdapter, git_version
from core.benchmarks.paths import GAIA_ROOT
from core.benchmarks.schema import BenchTask


class GAIAAdapter(BenchmarkAdapter):
    name = "gaia"
    license = "see HuggingFace dataset card"
    url = "https://huggingface.co/datasets/gaia-benchmark/GAIA"

    def available(self) -> bool:
        return GAIA_ROOT.exists() and any(GAIA_ROOT.glob("*.json*"))

    def version(self) -> str:
        return git_version(GAIA_ROOT) if GAIA_ROOT.exists() else "unknown"

    def note(self) -> str:
        return "通用助手多步任务；165 条 validation 已下载（gated，需 HF token）。"

    def load(self) -> list[BenchTask]:
        if not self.available():
            return []
        rows = []
        for path in sorted(GAIA_ROOT.glob("*.json*")):
            items = []
            if path.suffix == ".jsonl":
                items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                payload = json.loads(path.read_text(encoding="utf-8"))
                items = payload if isinstance(payload, list) else [payload]
            for index, item in enumerate(items):
                question = item.get("Question") or item.get("question") or ""
                rows.append(BenchTask(
                    id=f"gaia-{item.get('task_id', index)}",
                    source=self.name,
                    source_version=self.version(),
                    split="validation",
                    category="general_assistant",
                    task_type="multi_step",
                    instruction=question,
                    grader="mixed",
                    environment={"kind": "gaia", "runner": "native"},
                    success_criteria=[{"type": "answer", "value": item.get("Final answer") or item.get("final_answer") or ""}],
                    difficulty=str(item.get("Level") or item.get("level") or "unknown"),
                    license=self.license,
                    url=self.url,
                    metadata={"file_name": item.get("file_name"), "raw_id": item.get("task_id", index)},
                ))
        return rows
