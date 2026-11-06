# -*- coding: utf-8 -*-
"""评测接口冻结：本轮重构不改评测大框架，只锁住外部调用面。

锁三件事：
1. 统一 CLI 的子命令仍存在；
2. 数据集解析仍能从 core 侧拿到路径；
3. ``BenchTask`` 字段不因数据外置而漂移。
"""
from core.benchmarks.schema import BenchTask
from core.quality.paths import DATASETS_DIR, dataset_path
from core.quality.runner import build_parser

EXPECTED_COMMANDS = {
    "agent",
    "outcome",
    "rag",
    "public",
    "judge",
    "bfcl",
    "structured",
    "failures",
    "tau2",
}


def test_runner_cli_commands_are_stable():
    parser = build_parser()
    subparsers = next(
        action for action in parser._actions if action.dest == "command"
    )
    assert set(subparsers.choices) == EXPECTED_COMMANDS


def test_dataset_resolution_is_available_from_quality_layer():
    assert DATASETS_DIR.is_absolute()
    resolved = dataset_path("selfbuilt", "tasks.jsonl")
    assert resolved.is_absolute()
    assert resolved.name == "tasks.jsonl"


def test_benchtask_fields_are_stable():
    task = BenchTask(
        id="x",
        source="fixture",
        source_version="1",
        split="test",
        category="demo",
        task_type="tool_call",
        instruction="do it",
        grader="code",
        environment={"kind": "fixture", "runner": "native"},
    )
    payload = task.to_dict()
    for key in (
        "id", "source", "source_version", "split", "category", "task_type",
        "instruction", "grader", "environment", "bucket", "eval_scope",
        "success_criteria", "metadata",
    ):
        assert key in payload
