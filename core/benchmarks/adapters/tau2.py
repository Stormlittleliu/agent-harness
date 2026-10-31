# -*- coding: utf-8 -*-
"""τ²-bench retail 适配器：官方 tasks.json + split_tasks.json。"""
import json
from pathlib import Path

from core.benchmarks.adapters.base import BenchmarkAdapter, git_version
from core.benchmarks.paths import TAU2_ROOT
from core.benchmarks.schema import BenchTask

TASKS = TAU2_ROOT / "data" / "tau2" / "domains" / "retail" / "tasks.json"
SPLITS = TAU2_ROOT / "data" / "tau2" / "domains" / "retail" / "split_tasks.json"
POLICY = TAU2_ROOT / "data" / "tau2" / "domains" / "retail" / "policy.md"


class Tau2Adapter(BenchmarkAdapter):
    name = "tau2-bench"
    license = "MIT"
    url = "https://github.com/sierra-research/tau2-bench"

    def available(self) -> bool:
        return TASKS.exists() and SPLITS.exists()

    def version(self) -> str:
        return git_version(TAU2_ROOT)

    def note(self) -> str:
        return "零售客服多轮任务；工具/用户模拟器/数据库由 τ² 官方环境提供。"

    def load(self) -> list[BenchTask]:
        if not self.available():
            return []
        tasks = json.loads(TASKS.read_text(encoding="utf-8"))
        splits = json.loads(SPLITS.read_text(encoding="utf-8"))
        split_by_id = {
            str(task_id): split
            for split, ids in splits.items()
            for task_id in ids
        }

        rows = []
        for task in tasks:
            native_id = str(task.get("id"))
            instructions = (task.get("user_scenario") or {}).get("instructions") or {}
            instruction = (
                instructions.get("reason_for_call")
                or instructions.get("task_instructions")
                or (task.get("description") or {}).get("purpose")
                or ""
            )
            criteria = task.get("evaluation_criteria") or {}
            checks = []
            for action in criteria.get("actions") or []:
                checks.append({
                    "type": "action",
                    "name": action.get("name", ""),
                    "args": action.get("arguments") or {},
                })
            for assertion in criteria.get("nl_assertions") or []:
                text = assertion if isinstance(assertion, str) else assertion.get("nl_assertion", "")
                checks.append({"type": "nl_assertion", "text": text})
            for assertion in criteria.get("env_assertions") or []:
                checks.append({"type": "env_assertion", "raw": assertion})
            for check in criteria.get("communicate_checks") or []:
                checks.append({"type": "communicate", "raw": check})

            rows.append(BenchTask(
                id=f"tau2-retail-{native_id}",
                source=self.name,
                source_version=self.version(),
                split=split_by_id.get(native_id, "unknown"),
                category="customer_service",
                task_type="multi_turn_tool",
                instruction=instruction,
                grader="mixed",
                bucket="multi_turn",
                environment={
                    "kind": "tau2",
                    "domain": "retail",
                    "native_task_id": native_id,
                    "runner": "external",
                    "command": (
                        "tau2 run --domain retail --agent-llm deepseek/deepseek-chat "
                        f"--task-ids {native_id} --num-trials 1"
                    ),
                },
                initial_state=task.get("initial_state") or {},
                tools=[],
                policy="",
                success_criteria=checks,
                license=self.license,
                url=self.url,
                metadata={
                    "policy_path": str(POLICY),
                    "user_scenario": task.get("user_scenario"),
                    "reward_basis": criteria.get("reward_basis"),
                },
            ))
        return rows
