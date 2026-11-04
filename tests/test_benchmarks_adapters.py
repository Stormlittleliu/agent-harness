# -*- coding: utf-8 -*-
"""三个新增适配器的字段归一化；不依赖本机 benchmark 目录。"""
import gzip
import json
from pathlib import Path

from core.benchmarks.runner import get_runner
from core.benchmarks.schema import BenchTask


def test_cfbench_adapter_maps_constraints(monkeypatch, tmp_path):
    from core.benchmarks.adapters import cfbench

    data = tmp_path / "cfbench_data.json"
    data.write_text(json.dumps([{
        "idx": 0,
        "prompt": "写一段话",
        "split": "hard",
        "isanswer": "否",
        "gold": "",
        "criteria": [["三个段落", "次需", "数值约束", "段落数值约束"]],
        "doamin": "通用工作",
        "scenario": "办公效率",
        "source": "x",
    }], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(cfbench, "DATA", data)
    monkeypatch.setattr(cfbench, "CFBENCH_ROOT", tmp_path)

    task = cfbench.CFBenchAdapter().load()[0]
    assert task.id == "cfbench-0"
    assert task.category == "hard_unanswerable"
    assert task.grader == "mixed"
    assert task.environment["runner"] == "native"
    assert task.success_criteria == [{
        "type": "constraint",
        "value": "三个段落",
        "priority": "次需",
        "kind": "数值约束",
        "family": "段落数值约束",
    }]


def test_humaneval_adapter_keeps_unit_test(monkeypatch, tmp_path):
    from core.benchmarks.adapters import humaneval

    data = tmp_path / "HumanEval.jsonl.gz"
    with gzip.open(data, "wt", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "task_id": "HumanEval/0",
            "prompt": "def f():\n    pass\n",
            "entry_point": "f",
            "canonical_solution": "    return 1\n",
            "test": "def check(candidate):\n    assert candidate() == 1\n",
        }) + "\n")
    monkeypatch.setattr(humaneval, "DATA", data)
    monkeypatch.setattr(humaneval, "HUMANEVAL_ROOT", tmp_path)

    task = humaneval.HumanEvalAdapter().load()[0]
    assert task.id == "humaneval-HumanEval-0"
    assert task.grader == "unit_test"
    assert task.environment["runner"] == "sandbox_required"
    assert task.success_criteria[0]["entry_point"] == "f"


def test_mbpp_adapter_does_not_leak_solution(monkeypatch, tmp_path):
    from core.benchmarks.adapters import mbpp

    data = tmp_path / "mbpp.jsonl"
    data.write_text(json.dumps({
        "task_id": 1,
        "text": "write f",
        "code": "def f(): return 1",
        "test_setup_code": "",
        "test_list": ["assert f() == 1"],
        "challenge_test_list": [],
    }) + "\n", encoding="utf-8")
    monkeypatch.setattr(mbpp, "DATA", data)
    monkeypatch.setattr(mbpp, "MBPP_ROOT", tmp_path)

    task = mbpp.MBPPAdapter().load()[0]
    assert task.id == "mbpp-1"
    assert "code" not in task.metadata
    assert task.success_criteria[0]["tests"] == ["assert f() == 1"]


def test_cfbench_runner_requires_judge():
    task = BenchTask(
        id="cfbench-0",
        source="cfbench",
        source_version="x",
        split="hard",
        category="hard_unanswerable",
        task_type="constraint_following",
        instruction="写一段话",
        grader="mixed",
        environment={"kind": "cfbench", "runner": "native"},
    )
    result = get_runner(task).run(task)
    assert result.status == "judge_required"


def test_eval_layers_do_not_guess_scenario():
    from core.quality.eval_layers import MODEL_CAPABILITY, describe

    assert describe("unknown-benchmark")["eval_scope"] == MODEL_CAPABILITY
    assert describe("unknown-benchmark")["execution"] == "unknown"
    bfcl = describe("BFCL-v4")
    assert bfcl["eval_scope"] == "scenario_tool"
    assert bfcl["execution"] == "harness_required"
