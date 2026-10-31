# -*- coding: utf-8 -*-
"""BFCL v4 适配器：simple_python + irrelevance，官方数据。"""
import json
from pathlib import Path

from core.benchmarks.adapters.base import BenchmarkAdapter, git_version
from core.benchmarks.paths import BFCL_ROOT
from core.benchmarks.schema import BenchTask

DATA = BFCL_ROOT / "bfcl_eval" / "data"
SIMPLE = DATA / "BFCL_v4_simple_python.json"
SIMPLE_GT = DATA / "possible_answer" / "BFCL_v4_simple_python.json"
IRRELEVANCE = DATA / "BFCL_v4_irrelevance.json"


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def first_user_text(item) -> str:
    parts = []
    for turn in item.get("question", []):
        for message in turn:
            if message.get("role") == "user":
                parts.append(message.get("content", ""))
    return "\n".join(parts)


class BFCLAdapter(BenchmarkAdapter):
    name = "bfcl-v4"
    license = "Apache-2.0"
    url = "https://github.com/ShishirPatil/gorilla"

    def available(self) -> bool:
        return SIMPLE.exists() and IRRELEVANCE.exists()

    def version(self) -> str:
        return git_version(BFCL_ROOT)

    def note(self) -> str:
        return "工具调用能力；官方数据，官方评分是 AST/可执行匹配。"

    def load(self) -> list[BenchTask]:
        if not self.available():
            return []
        ground_truth = {
            row["id"]: row.get("ground_truth", [])
            for row in read_jsonl(SIMPLE_GT)
        } if SIMPLE_GT.exists() else {}

        rows = []
        for item in read_jsonl(SIMPLE):
            expected = ground_truth.get(item["id"]) or []
            first = expected[0] if expected else {}
            checks = []
            if first:
                name = next(iter(first))
                checks.append({"type": "function_call", "name": name, "args": first[name]})
            rows.append(BenchTask(
                id=f"bfcl-{item['id']}",
                source=self.name,
                source_version=self.version(),
                split="test",
                category="tool_calling_simple",
                task_type="single_turn_tool",
                instruction=first_user_text(item),
                grader="code",
                bucket="capability",
                environment={
                    "kind": "bfcl",
                    "test_category": "simple_python",
                    "native_task_id": item["id"],
                    "runner": "external",
                    "command": (
                        "bfcl generate --model DeepSeek-V3.2-Exp-FC "
                        "--test-category simple_python --run-ids && "
                        "bfcl evaluate --model DeepSeek-V3.2-Exp-FC "
                        "--test-category simple_python"
                    ),
                },
                tools=item.get("function") or [],
                success_criteria=checks,
                license=self.license,
                url=self.url,
                metadata={"bfcl_id": item["id"]},
            ))

        for item in read_jsonl(IRRELEVANCE):
            rows.append(BenchTask(
                id=f"bfcl-{item['id']}",
                source=self.name,
                source_version=self.version(),
                split="test",
                category="tool_calling_irrelevance",
                task_type="single_turn_tool",
                instruction=first_user_text(item),
                grader="code",
                bucket="adversarial",
                environment={
                    "kind": "bfcl",
                    "test_category": "irrelevance",
                    "native_task_id": item["id"],
                    "runner": "external",
                    "command": (
                        "bfcl generate --model DeepSeek-V3.2-Exp-FC "
                        "--test-category irrelevance --run-ids && "
                        "bfcl evaluate --model DeepSeek-V3.2-Exp-FC "
                        "--test-category irrelevance"
                    ),
                },
                tools=item.get("function") or [],
                success_criteria=[{"type": "no_tool_call"}],
                license=self.license,
                url=self.url,
                metadata={"bfcl_id": item["id"]},
            ))
        return rows
