# -*- coding: utf-8 -*-
"""从公开 benchmark 抽取 Demo 用的小样本。"""
from __future__ import annotations

import json
import random
from pathlib import Path

from core.benchmarks.paths import BFCL_ROOT, MULTIHOP_ROOT

BFCL_DATA = BFCL_ROOT / "bfcl_eval" / "data"
BFCL_SIMPLE = BFCL_DATA / "BFCL_v4_simple_python.json"
BFCL_GT = BFCL_DATA / "possible_answer" / "BFCL_v4_simple_python.json"
BFCL_IRRELEVANCE = BFCL_DATA / "BFCL_v4_irrelevance.json"
MULTIHOP_QUERIES = MULTIHOP_ROOT / "data" / "MultiHopRAG.json"
MULTIHOP_CORPUS = MULTIHOP_ROOT / "data" / "corpus.json"


def _read_jsonl(path: Path):
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _first_user_text(item) -> str:
    parts = []
    for turn in item.get("question", []):
        for message in turn:
            if message.get("role") == "user":
                parts.append(message.get("content", ""))
    return "\n".join(parts)


def load_bfcl_cases(n_simple: int = 15, n_irrelevance: int = 5, seed: int = 42):
    rng = random.Random(seed)
    ground_truth = {
        row["id"]: row.get("ground_truth", [])
        for row in _read_jsonl(BFCL_GT)
    }
    simple = list(_read_jsonl(BFCL_SIMPLE))
    irrelevance = list(_read_jsonl(BFCL_IRRELEVANCE))

    cases = []
    for item in rng.sample(simple, min(n_simple, len(simple))):
        expected = ground_truth.get(item["id"]) or []
        cases.append({
            "id": item["id"],
            "kind": "simple",
            "question": _first_user_text(item),
            "functions": item.get("function") or [],
            "expected_calls": expected,
        })
    for item in rng.sample(irrelevance, min(n_irrelevance, len(irrelevance))):
        cases.append({
            "id": item["id"],
            "kind": "irrelevance",
            "question": _first_user_text(item),
            "functions": item.get("function") or [],
            "expected_calls": [],
        })
    return cases


def load_multihop_cases(n_per_type: int = 5, seed: int = 42):
    rng = random.Random(seed)
    queries = json.loads(MULTIHOP_QUERIES.read_text(encoding="utf-8"))
    grouped = {}
    for item in queries:
        grouped.setdefault(item.get("question_type"), []).append(item)

    cases = []
    for question_type in sorted(grouped):
        if question_type == "null_query":
            continue
        for index, item in enumerate(rng.sample(grouped[question_type], min(n_per_type, len(grouped[question_type])))):
            cases.append({
                "id": f"multihop-{question_type}-{index}",
                "question": item["query"],
                "answer": item.get("answer", ""),
                "question_type": question_type,
                "evidence_titles": [
                    evidence.get("title", "")
                    for evidence in item.get("evidence_list", [])
                ],
            })
    return cases


def load_multihop_corpus():
    return json.loads(MULTIHOP_CORPUS.read_text(encoding="utf-8"))
