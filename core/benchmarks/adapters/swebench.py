# -*- coding: utf-8 -*-
"""SWE-bench 适配器：读取本地 JSON/JSONL；执行需要 Docker。"""
import json

from core.benchmarks.adapters.base import BenchmarkAdapter, git_version
from core.benchmarks.paths import SWEBENCH_ROOT
from core.benchmarks.schema import BenchTask


def _as_list(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return [value]
    return value or []


class SWEBenchAdapter(BenchmarkAdapter):
    name = "swe-bench"
    license = "MIT (see repo)"
    url = "https://github.com/princeton-nlp/SWE-bench"

    def available(self) -> bool:
        return SWEBENCH_ROOT.exists() and any(SWEBENCH_ROOT.glob("*.json*"))

    def version(self) -> str:
        return git_version(SWEBENCH_ROOT) if SWEBENCH_ROOT.exists() else "unknown"

    def note(self) -> str:
        return "GitHub issue 修复；每个 instance 需要 Docker 仓库环境。"

    def load(self) -> list[BenchTask]:
        if not self.available():
            return []
        rows = []
        for path in sorted(SWEBENCH_ROOT.glob("*.json*")):
            if path.suffix == ".jsonl":
                items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                payload = json.loads(path.read_text(encoding="utf-8"))
                items = payload if isinstance(payload, list) else [payload]
            for item in items:
                instance_id = item.get("instance_id", "")
                rows.append(BenchTask(
                    id=f"swebench-{instance_id}",
                    source=self.name,
                    source_version=self.version(),
                    split="test",
                    category="coding",
                    task_type="code_repair",
                    instruction=item.get("problem_statement", ""),
                    grader="code",
                    environment={
                        "kind": "swebench",
                        "runner": "external",
                        "repo": item.get("repo", ""),
                        "base_commit": item.get("base_commit", ""),
                        "docker": True,
                    },
                    initial_state={
                        "repo": item.get("repo", ""),
                        "base_commit": item.get("base_commit", ""),
                    },
                    success_criteria=[{
                        "type": "tests",
                        "fail_to_pass": _as_list(item.get("FAIL_TO_PASS")),
                        "pass_to_pass": _as_list(item.get("PASS_TO_PASS")),
                    }],
                    license=self.license,
                    url=self.url,
                    metadata={"instance_id": instance_id, "test_patch": item.get("test_patch", "")},
                ))
        return rows
