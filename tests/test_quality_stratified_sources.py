# -*- coding: utf-8 -*-
"""新增的三个源：CFBench / HumanEval / MBPP 的抽样与执行边界。"""
import gzip
import json
from pathlib import Path

from core.benchmarks.runner import get_runner
from core.benchmarks.schema import BenchTask
from core.quality.stratified import build_all


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _write_gz_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _fake_root(tmp_path: Path) -> Path:
    root = tmp_path / "bench"

    cfbench = []
    index = 0
    for split in ("easy", "hard"):
        for answer in ("是", "否"):
            for number in range(8):
                cfbench.append({
                    "idx": index,
                    "prompt": f"{split}-{answer}-{number}",
                    "split": split,
                    "isanswer": answer,
                    "gold": "gold" if answer == "是" else "",
                    "criteria": [["约束", "主需", "内容约束", "内容"]],
                    "doamin": "通用工作",
                    "scenario": "办公效率",
                    "source": "x",
                })
                index += 1
    cfbench.append({
        "idx": index,
        "prompt": "missing-isanswer",
        "split": "hard",
        "isanswer": "",
        "gold": "",
        "criteria": [],
        "doamin": "",
        "scenario": "",
        "source": "x",
    })
    (root / "CFBench" / "data").mkdir(parents=True, exist_ok=True)
    (root / "CFBench" / "data" / "cfbench_data.json").write_text(
        json.dumps(cfbench, ensure_ascii=False), encoding="utf-8"
    )

    _write_gz_jsonl(
        root / "human-eval" / "data" / "HumanEval.jsonl.gz",
        [
            {
                "task_id": f"HumanEval/{number}",
                "prompt": f"def f{number}():\n    pass\n",
                "entry_point": f"f{number}",
                "canonical_solution": "    return 1\n",
                "test": f"def check(candidate):\n    assert candidate() == 1\n",
            }
            for number in range(8)
        ],
    )

    _write_jsonl(
        root / "mbpp" / "mbpp.jsonl",
        [
            {
                "task_id": number + 1,
                "text": f"write f{number}",
                "code": f"def f{number}(): return 1",
                "test_setup_code": "",
                "test_list": [f"assert f{number}() == 1"],
                "challenge_test_list": [],
            }
            for number in range(8)
        ],
    )
    return root


def test_new_sources_are_grouped_and_traceable(tmp_path):
    root = _fake_root(tmp_path)
    out = tmp_path / "out"
    manifest = build_all(
        root,
        out,
        per_category=5,
        seed=42,
        sources=("cfbench", "humaneval", "mbpp"),
    )

    assert manifest["sets"]["cfbench"]["counts"] == {
        "easy_answerable": 5,
        "easy_unanswerable": 5,
        "hard_answerable": 5,
        "hard_unanswerable": 5,
        "hard_unknown": 1,
    }
    assert manifest["sets"]["humaneval"]["counts"] == {"function_completion": 5}
    assert manifest["sets"]["mbpp"]["counts"] == {"function_generation": 5}
    assert manifest["selection_record"]["by_eval_scope"] == {"model_capability": 31}

    selections = [
        json.loads(line)
        for line in (out / "selections.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(selections) == 21 + 5 + 5
    for item in selections:
        assert item["source_index"] is not None
        assert item["source_index"] >= 0
        assert len(item["source_sha256"]) == 16
        assert item["source_id"]


def test_code_tasks_do_not_pretend_to_run():
    task = BenchTask(
        id="humaneval-HumanEval-0",
        source="humaneval",
        source_version="x",
        split="test",
        category="function_completion",
        task_type="code_generation",
        instruction="def f(): pass",
        grader="unit_test",
        environment={"kind": "humaneval", "runner": "sandbox_required"},
        success_criteria=[{"type": "unit_test", "test": "assert True"}],
    )
    result = get_runner(task).run(task)
    assert result.status == "sandbox_required"
    assert "沙箱" in result.error
