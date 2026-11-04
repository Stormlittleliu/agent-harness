# -*- coding: utf-8 -*-
"""分层抽样：每类 5 条、确定性、出处记录完整。"""
import json
from pathlib import Path

from core.quality.stratified import build_all, sample_with_index


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _fake_root(tmp_path: Path) -> Path:
    root = tmp_path / "bench"
    bfcl = root / "BFCL" / "berkeley-function-call-leaderboard" / "bfcl_eval" / "data"
    _write_jsonl(
        bfcl / "BFCL_v4_simple_python.json",
        [{"id": f"simple_python_{i}", "question": f"q{i}", "function": []} for i in range(8)],
    )
    _write_jsonl(
        bfcl / "BFCL_v4_multiple.json",
        [{"id": f"multiple_{i}", "question": f"q{i}", "function": []} for i in range(8)],
    )
    rgb = root / "RGB" / "data"
    for language in ("zh", "en"):
        for split in ("refine", "int", "fact"):
            _write_jsonl(
                rgb / f"{language}_{split}.json",
                [{"id": f"{language}-{split}-{i}", "query": f"q{i}", "answer": f"a{i}", "positive": [], "negative": []} for i in range(8)],
            )
    domains = root / "tau2-bench" / "data" / "tau2" / "domains"
    for domain in ("airline", "banking_knowledge", "retail", "telecom"):
        path = domains / domain / "tasks.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([{"id": f"{domain}-{i}", "description": f"d{i}"} for i in range(8)]),
            encoding="utf-8",
        )
    multihop = root / "MultiHop-RAG" / "data" / "MultiHopRAG.json"
    multihop.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for kind in ("comparison_query", "inference_query", "temporal_query", "null_query"):
        rows.extend({"query": f"{kind}-{i}", "question_type": kind} for i in range(8))
    multihop.write_text(json.dumps(rows), encoding="utf-8")
    return root


def test_sample_with_index_is_deterministic():
    rows = [{"id": str(i)} for i in range(20)]
    first = sample_with_index(rows, per_category=5, seed=42, category="x")
    second = sample_with_index(rows, per_category=5, seed=42, category="x")
    assert len(first) == 5
    assert [pair[0] for pair in first] == [pair[0] for pair in second]
    assert all(0 <= index < len(rows) for index, _ in first)


def test_build_all_records_every_pick(tmp_path):
    root = _fake_root(tmp_path)
    out = tmp_path / "out"
    manifest = build_all(
        root,
        out,
        per_category=5,
        seed=42,
        sources=("bfcl", "rgb", "tau2", "multihop"),
    )

    expected = sum(len(info["counts"]) * 5 for info in manifest["sets"].values())
    assert manifest["selection_record"]["count"] == expected
    # 每个集合的每类都是 5 条
    for info in manifest["sets"].values():
        assert set(info["counts"].values()) == {5}

    selections = [
        json.loads(line)
        for line in (out / "selections.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(selections) == manifest["selection_record"]["count"]
    for item in selections:
        assert len(item["source_sha256"]) == 16
        assert item["source_index"] >= 0
        assert item["source_id"]
        assert item["source_size"] >= 5
    assert (out / "selections.md").is_file()
    assert (out / "manifest.json").is_file()
