# -*- coding: utf-8 -*-
"""榜单环境 runner 接口。

三种执行方式：
- external：调用官方 harness（τ² / BFCL / SWE-bench / WebArena / OSWorld）；
- native：用本项目的 Agent/RAG 工具执行（RGB / MultiHop / GAIA）；
- data_only：只提供数据，环境未安装。

安全默认：execute=False，只返回将要执行的命令，不自动跑。
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

from core.benchmarks.schema import BenchTask


@dataclass
class RunnerResult:
    task_id: str
    status: str
    command: str = ""
    returncode: int | None = None
    output: str = ""
    error: str = ""
    metadata: dict = field(default_factory=dict)
    probe: bool = False


class BenchmarkRunner:
    def run(self, task: BenchTask, execute: bool = False) -> RunnerResult:
        raise NotImplementedError


class ExternalRunner(BenchmarkRunner):
    def run(self, task: BenchTask, execute: bool = False) -> RunnerResult:
        command = task.environment.get("command", "")
        if not command:
            return RunnerResult(
                task_id=task.id,
                status="environment_required",
                error=f"{task.environment.get('kind')} 需要先准备官方环境",
                metadata=task.environment,
            )
        if not execute:
            return RunnerResult(task_id=task.id, status="prepared", command=command, metadata=task.environment)
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=task.environment.get("timeout_seconds", 600),
        )
        return RunnerResult(
            task_id=task.id,
            status="completed" if completed.returncode == 0 else "failed",
            command=command,
            returncode=completed.returncode,
            output=completed.stdout[-4000:],
            error=completed.stderr[-4000:],
            metadata=task.environment,
        )


class NativeRunner(BenchmarkRunner):
    def run(self, task: BenchTask, execute: bool = False) -> RunnerResult:
        return RunnerResult(
            task_id=task.id,
            status="native_adapter_required",
            error=(
                "该数据集需要映射到本项目的 Agent/工具；"
                "检索任务可先用 core.quality.multihop_full / core.quality.public_sample。"
            ),
            metadata=task.environment,
            probe=True,
        )


class DataOnlyRunner(BenchmarkRunner):
    def run(self, task: BenchTask, execute: bool = False) -> RunnerResult:
        return RunnerResult(
            task_id=task.id,
            status="data_only",
            error="只加载了任务元数据，执行环境未安装",
            metadata=task.environment,
            probe=True,
        )


class SandboxRunner(BenchmarkRunner):
    """代码题需要执行沙箱；本仓库还没有，所以明确拒绝而不是假装跑过。"""

    def run(self, task: BenchTask, execute: bool = False) -> RunnerResult:
        return RunnerResult(
            task_id=task.id,
            status="sandbox_required",
            error="需要 Python 执行沙箱（子进程 + 超时 + 禁网）；当前未接。",
            metadata=task.environment,
            probe=True,
        )


class JudgeRunner(BenchmarkRunner):
    """约束遵循题需要逐条 judge；judge 未接时明确返回，不冒充已评分。"""

    def run(self, task: BenchTask, execute: bool = False) -> RunnerResult:
        return RunnerResult(
            task_id=task.id,
            status="judge_required",
            error="需要 LLM judge 逐条判约束；当前未接。",
            metadata=task.environment,
            probe=True,
        )


RUNNERS = {
    "tau2": ExternalRunner(),
    "bfcl": ExternalRunner(),
    "swebench": ExternalRunner(),
    "webarena": ExternalRunner(),
    "osworld": ExternalRunner(),
    "rgb": NativeRunner(),
    "multihop": NativeRunner(),
    "gaia": NativeRunner(),
    "cfbench": JudgeRunner(),
    "humaneval": SandboxRunner(),
    "mbpp": SandboxRunner(),
}


def get_runner(task: BenchTask) -> BenchmarkRunner:
    kind = task.environment.get("kind", "")
    return RUNNERS.get(kind, DataOnlyRunner())


def run_task(task: BenchTask, execute: bool = False) -> RunnerResult:
    """Probe：返回“这条任务需要什么环境/命令”，不承诺已经执行。

    真正可执行的只有装了官方环境的 ExternalRunner；其余 status 都是
    ``*_required``，调用方不要把它当成“跑过”的证据。
    """
    return get_runner(task).run(task, execute=execute)
