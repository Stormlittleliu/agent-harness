# -*- coding: utf-8 -*-
"""按类别从公开 benchmark 源抽平衡样本（默认每类 5 条），并记录抽样出处。

这不是替代官方 benchmark，也不是“跑分”：它只解决一个问题——
现有抽样集类别覆盖不均（BFCL 只测两类、RGB 只有中文 refine/int/fact、
τ² 只有 retail），面试/复盘时容易把“小样本”讲成“全量能力”。

每次生成都会写一份**抽样出处记录**：

- ``data/evals/datasets/stratified/selections.jsonl``：一条一个被选中的样本，
  记录 benchmark / category / 源文件 / 源文件 hash / 源行号 / 源 id / seed；
- ``data/evals/datasets/stratified/selections.md``：按类别汇总的可读表；
- ``manifest.json`` 里也保留同样的 sets 摘要和 selection_record 路径。

产物与现有评测集分开，不覆盖。

用法::

    python -m core.quality.stratified --per-category 5 --seed 42
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

OUT_DIR = Path("data/evals/datasets/stratified")
DEFAULT_BENCH_ROOT = Path(r"E:\CODE\benchmarks")
DEFAULT_PER_CATEGORY = 5
DEFAULT_SEED = 42


def _read_rows(path: Path) -> list[dict[str, Any]]:
    """兼容 JSONL 和 pretty-printed JSON array（BFCL 有些文件是数组）。"""
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        return [data]
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            item = json.loads(line)
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _read_gz_jsonl(path: Path) -> list[dict[str, Any]]:
    """HumanEval 的题面在 .jsonl.gz 里；逐行读，保留原始行号。"""
    import gzip

    rows: list[dict[str, Any]] = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                item = json.loads(line)
                if isinstance(item, dict):
                    rows.append(item)
    return rows


def _row_id(row: dict[str, Any]) -> str:
    """源 id 的稳定字符串；保持既有口径，不在这次扩源时重排旧样本。"""
    return str(row.get("id") or row.get("task_id") or row.get("query") or "")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def sample_with_index(
    rows: list[dict[str, Any]],
    *,
    per_category: int,
    seed: int | str,
    category: str,
) -> list[tuple[int, dict[str, Any]]]:
    """确定性抽样：先按 id 排序，再用 seed+category 抽，避免“前 N 条”偏差。

    返回 ``(源行号, 行)``；源行号是原始文件里的 0-based 下标，用于出处记录。
    """
    indexed = list(enumerate(rows))
    indexed.sort(key=lambda pair: _row_id(pair[1]))
    if per_category <= 0 or len(indexed) <= per_category:
        return indexed
    rng = random.Random(f"{seed}:{category}")
    return sorted(rng.sample(indexed, per_category), key=lambda pair: _row_id(pair[1]))


def _sample_indexed(
    pairs: list[tuple[int, dict[str, Any]]],
    *,
    per_category: int,
    seed: int | str,
    category: str,
) -> list[tuple[int, dict[str, Any]]]:
    """和 sample_with_index 同样的规则，但接受带原始行号的 (index, row)。"""
    ordered = sorted(pairs, key=lambda pair: _row_id(pair[1]))
    if per_category <= 0 or len(ordered) <= per_category:
        return ordered
    rng = random.Random(f"{seed}:{category}")
    return sorted(rng.sample(ordered, per_category), key=lambda pair: _row_id(pair[1]))


def select_row(
    *,
    benchmark: str,
    category: str,
    source_path: Path,
    source_index: int | None,
    source_row: dict[str, Any],
    seed: int,
    per_category: int,
    source_sha: str,
    source_size: int,
) -> dict[str, Any]:
    """一条被选中样本的溯源记录；JSONL 里一条一行。"""
    return {
        "benchmark": benchmark,
        "category": category,
        "source": source_path.as_posix(),
        "source_file": source_path.name,
        "source_sha256": source_sha,
        "source_size": source_size,
        "source_index": source_index,
        "source_id": _row_id(source_row),
        "output_id": _row_id(source_row),
        "seed": seed,
        "per_category": per_category,
    }


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def build_bfcl(
    root: Path, out_dir: Path, *, per_category: int, seed: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data_dir = root / "BFCL" / "berkeley-function-call-leaderboard" / "bfcl_eval" / "data"
    files = sorted(data_dir.glob("BFCL_v4_*.json"))
    rows: list[dict[str, Any]] = []
    selections: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    sources: dict[str, int] = {}
    skipped: dict[str, str] = {}
    source_hashes: dict[str, str] = {}
    for path in files:
        category = path.stem.removeprefix("BFCL_v4_")
        items = [item for item in _read_rows(path) if "question" in item]
        if not items:
            # format_sensitivity 是 {category: [case_id]} 的索引文件，没有题目正文；
            # 不把它伪装成样本。
            skipped[category] = "没有 question 字段（索引文件）"
            continue
        source_sha = _sha256(path)
        sources[category] = len(items)
        source_hashes[path.name] = source_sha
        picked = sample_with_index(
            items, per_category=per_category, seed=seed, category=f"bfcl:{category}"
        )
        counts[category] = len(picked)
        for index, item in picked:
            rows.append({
                "benchmark": "BFCL-v4",
                "category": category,
                "source_file": path.name,
                **item,
            })
            selections.append(select_row(
                benchmark="BFCL-v4",
                category=category,
                source_path=path,
                source_index=index,
                source_row=item,
                seed=seed,
                per_category=per_category,
                source_sha=source_sha,
                source_size=len(items),
            ))
    _write_jsonl(out_dir / "bfcl_5per_category.jsonl", rows)
    return (
        {
            "file": "bfcl_5per_category.jsonl",
            "source": data_dir.as_posix(),
            "counts": counts,
            "source_sizes": sources,
            "source_sha256": source_hashes,
            "skipped": skipped,
        },
        selections,
    )


def build_rgb(
    root: Path, out_dir: Path, *, per_category: int, seed: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data_dir = root / "RGB" / "data"
    groups = {
        "normal": ("zh_refine.json", "en_refine.json"),
        "integration": ("zh_int.json", "en_int.json"),
        "counterfactual": ("zh_fact.json", "en_fact.json"),
    }
    rows: list[dict[str, Any]] = []
    selections: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    sources: dict[str, int] = {}
    source_hashes: dict[str, str] = {}
    for category, filenames in groups.items():
        for filename in filenames:
            path = data_dir / filename
            language = filename.split("_", 1)[0]
            key = f"{language}_{category}"
            items = _read_rows(path)
            source_sha = _sha256(path)
            sources[key] = len(items)
            source_hashes[path.name] = source_sha
            picked = sample_with_index(
                items, per_category=per_category, seed=seed, category=f"rgb:{key}"
            )
            counts[key] = len(picked)
            for index, item in picked:
                rows.append({
                    "benchmark": "RGB",
                    "category": category,
                    "language": language,
                    "source_split": path.stem,
                    **item,
                })
                selections.append(select_row(
                    benchmark="RGB",
                    category=key,
                    source_path=path,
                    source_index=index,
                    source_row=item,
                    seed=seed,
                    per_category=per_category,
                    source_sha=source_sha,
                    source_size=len(items),
                ))
    _write_jsonl(out_dir / "rgb_5per_category.jsonl", rows)
    return (
        {
            "file": "rgb_5per_category.jsonl",
            "source": data_dir.as_posix(),
            "counts": counts,
            "source_sizes": sources,
            "source_sha256": source_hashes,
            "note": "RGB 的 rejection 不是独立源文件，未伪造该类别；只在 refine/int/fact 三类抽样。",
        },
        selections,
    )


def build_tau2(
    root: Path, out_dir: Path, *, per_category: int, seed: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data_dir = root / "tau2-bench" / "data" / "tau2" / "domains"
    domains = ("airline", "banking_knowledge", "retail", "telecom")
    rows: list[dict[str, Any]] = []
    selections: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    sources: dict[str, int] = {}
    source_hashes: dict[str, str] = {}
    for domain in domains:
        path = data_dir / domain / "tasks.json"
        if not path.is_file():
            continue
        tasks = json.loads(path.read_text(encoding="utf-8"))
        source_sha = _sha256(path)
        sources[domain] = len(tasks)
        source_hashes[f"{domain}/tasks.json"] = source_sha
        picked = sample_with_index(
            tasks, per_category=per_category, seed=seed, category=f"tau2:{domain}"
        )
        counts[domain] = len(picked)
        for index, task in picked:
            rows.append({"benchmark": "tau2-bench", "domain": domain, **task})
            selections.append(select_row(
                benchmark="tau2-bench",
                category=domain,
                source_path=path,
                source_index=index,
                source_row=task,
                seed=seed,
                per_category=per_category,
                source_sha=source_sha,
                source_size=len(tasks),
            ))
    _write_jsonl(out_dir / "tau2_5per_domain.jsonl", rows)
    return (
        {
            "file": "tau2_5per_domain.jsonl",
            "source": data_dir.as_posix(),
            "counts": counts,
            "source_sizes": sources,
            "source_sha256": source_hashes,
        },
        selections,
    )


def build_multihop(
    root: Path, out_dir: Path, *, per_category: int, seed: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = root / "MultiHop-RAG" / "data" / "MultiHopRAG.json"
    rows = json.loads(path.read_text(encoding="utf-8"))
    source_sha = _sha256(path)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("question_type") or "unknown"), []).append(row)
    picked_rows: list[dict[str, Any]] = []
    selections: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    sources: dict[str, int] = {}
    for category, items in sorted(grouped.items()):
        sources[category] = len(items)
        picked = sample_with_index(
            items, per_category=per_category, seed=seed, category=f"multihop:{category}"
        )
        counts[category] = len(picked)
        for index, item in picked:
            picked_rows.append({"benchmark": "MultiHop-RAG", "category": category, **item})
            selections.append(select_row(
                benchmark="MultiHop-RAG",
                category=category,
                source_path=path,
                source_index=index,
                source_row=item,
                seed=seed,
                per_category=per_category,
                source_sha=source_sha,
                source_size=len(items),
            ))
    _write_jsonl(out_dir / "multihop_5per_type.jsonl", picked_rows)
    return (
        {
            "file": "multihop_5per_type.jsonl",
            "source": path.as_posix(),
            "counts": counts,
            "source_sizes": sources,
            "source_sha256": {path.name: source_sha},
            "note": "null_query 也保留；全量评测另有 outputs/public/multihop_full.json。",
        },
        selections,
    )


def build_from_adapter(
    root: Path,
    out_dir: Path,
    *,
    benchmark: str,
    adapter_name: str,
    category_fn,
    source_path: Path,
    source_file: str,
    output_file: str,
    per_category: int,
    seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """用现有 BenchTask 适配器抽 5 条/类；没有原始行号，用 task id 溯源。"""
    from core.benchmarks.adapters import get_adapter

    adapter = get_adapter(adapter_name)
    tasks = adapter.load()
    if not tasks:
        return (
            {
                "file": output_file,
                "source": source_path.as_posix(),
                "counts": {},
                "source_sizes": {},
                "note": "adapter 不可用或没有任务",
            },
            [],
        )
    grouped: dict[str, list] = {}
    for task in tasks:
        grouped.setdefault(str(category_fn(task)), []).append(task)

    rows: list[dict[str, Any]] = []
    selections: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for category, items in sorted(grouped.items()):
        picked = sample_with_index(
            [item.to_dict() for item in items],
            per_category=per_category,
            seed=seed,
            category=f"{adapter_name}:{category}",
        )
        counts[category] = len(picked)
        for index, item in picked:
            task = items[index]
            data = item
            data.update({
                "benchmark": benchmark,
                "category": category,
                "source_category": task.category,
            })
            rows.append(data)
            selections.append(select_row(
                benchmark=benchmark,
                category=category,
                source_path=source_path,
                source_index=None,
                source_row=task.to_dict(),
                seed=seed,
                per_category=per_category,
                source_sha="",
                source_size=len(items),
            ))
    _write_jsonl(out_dir / output_file, rows)
    return (
        {
            "file": output_file,
            "source": source_path.as_posix(),
            "source_file": source_file,
            "counts": counts,
            "source_sizes": {name: len(items) for name, items in grouped.items()},
            "note": "来自现有 BenchTask 适配器；溯源用 source_id（task id），source_index 为空。",
        },
        selections,
    )


def build_gaia(
    root: Path, out_dir: Path, *, per_category: int, seed: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return build_from_adapter(
        root,
        out_dir,
        benchmark="GAIA",
        adapter_name="gaia",
        category_fn=lambda task: f"level_{task.difficulty}",
        source_path=root / "GAIA" / "gaia_validation.jsonl",
        source_file="gaia_validation.jsonl",
        output_file="gaia_5per_level.jsonl",
        per_category=per_category,
        seed=seed,
    )


def build_swebench(
    root: Path, out_dir: Path, *, per_category: int, seed: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return build_from_adapter(
        root,
        out_dir,
        benchmark="SWE-bench",
        adapter_name="swe-bench",
        category_fn=lambda task: str(task.environment.get("repo") or "unknown"),
        source_path=root / "SWE-bench" / "swebench_verified.jsonl",
        source_file="swebench_verified.jsonl",
        output_file="swebench_5per_repo.jsonl",
        per_category=per_category,
        seed=seed,
    )


def build_webarena(
    root: Path, out_dir: Path, *, per_category: int, seed: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return build_from_adapter(
        root,
        out_dir,
        benchmark="WebArena",
        adapter_name="webarena",
        category_fn=lambda task: "+".join(sorted(task.environment.get("sites") or [])) or "unknown",
        source_path=root / "WebArena" / "config_files",
        source_file="config_files/",
        output_file="webarena_5per_site.jsonl",
        per_category=per_category,
        seed=seed,
    )


def build_osworld(
    root: Path, out_dir: Path, *, per_category: int, seed: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return build_from_adapter(
        root,
        out_dir,
        benchmark="OSWorld",
        adapter_name="osworld",
        category_fn=lambda task: task.category,
        source_path=root / "OSWorld" / "evaluation_examples" / "examples",
        source_file="evaluation_examples/examples/",
        output_file="osworld_5per_category.jsonl",
        per_category=per_category,
        seed=seed,
    )


def build_cfbench(
    root: Path, out_dir: Path, *, per_category: int, seed: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """CFBench：按 split(easy/hard) × 是否可回答 分组。

    CFBench 的 ``doamin`` 混了领域和任务类型（200+ 个值），不适合当分层键；
    ``scenario`` 又有 102 条“其他”。真正影响判分的是难度和“这题有没有答案”，
    所以用这两条轴。
    """
    from core.benchmarks.adapters.cfbench import answerability

    path = root / "CFBench" / "data" / "cfbench_data.json"
    rows = _read_rows(path)
    source_sha = _sha256(path)
    grouped: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, row in enumerate(rows):
        key = f"{row.get('split') or 'unknown'}_{answerability(str(row.get('isanswer') or ''))}"
        grouped.setdefault(key, []).append((index, row))

    picked_rows: list[dict[str, Any]] = []
    selections: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    sources: dict[str, int] = {}
    for category, items in sorted(grouped.items()):
        sources[category] = len(items)
        picked = _sample_indexed(
            items, per_category=per_category, seed=seed, category=f"cfbench:{category}"
        )
        counts[category] = len(picked)
        for index, row in picked:
            # CFBench 上游没有 id，只有 idx；补一个稳定 id 供抽样排序与溯源。
            source_row = {"id": f"cfbench-{index}", **row}
            picked_rows.append({"benchmark": "CFBench", "category": category, **source_row})
            selections.append(select_row(
                benchmark="CFBench",
                category=category,
                source_path=path,
                source_index=index,
                source_row=source_row,
                seed=seed,
                per_category=per_category,
                source_sha=source_sha,
                source_size=len(items),
            ))
    _write_jsonl(out_dir / "cfbench_5per_split.jsonl", picked_rows)
    return (
        {
            "file": "cfbench_5per_split.jsonl",
            "source": path.as_posix(),
            "source_file": path.name,
            "counts": counts,
            "source_sizes": sources,
            "source_sha256": {path.name: source_sha},
            "note": "按 split × 是否可回答 分组；1 条缺 isanswer 单独成组。判分靠 LLM judge。",
        },
        selections,
    )


def build_humaneval(
    root: Path, out_dir: Path, *, per_category: int, seed: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """HumanEval：没有官方类别，单组抽 5 条；判分要执行单测。"""
    path = root / "human-eval" / "data" / "HumanEval.jsonl.gz"
    rows = _read_gz_jsonl(path)
    source_sha = _sha256(path)
    category = "function_completion"
    picked = sample_with_index(
        rows, per_category=per_category, seed=seed, category=f"humaneval:{category}"
    )
    picked_rows: list[dict[str, Any]] = []
    selections: list[dict[str, Any]] = []
    for index, item in picked:
        picked_rows.append({
            "benchmark": "HumanEval",
            "category": category,
            "task_id": item.get("task_id"),
            "prompt": item.get("prompt"),
            "entry_point": item.get("entry_point"),
            "test": item.get("test"),
        })
        selections.append(select_row(
            benchmark="HumanEval",
            category=category,
            source_path=path,
            source_index=index,
            source_row=item,
            seed=seed,
            per_category=per_category,
            source_sha=source_sha,
            source_size=len(rows),
        ))
    _write_jsonl(out_dir / "humaneval_5per_task.jsonl", picked_rows)
    return (
        {
            "file": "humaneval_5per_task.jsonl",
            "source": path.as_posix(),
            "source_file": path.name,
            "counts": {category: len(picked)},
            "source_sizes": {category: len(rows)},
            "source_sha256": {path.name: source_sha},
            "note": "无官方类别，单组 5 条；unit_test 判分，执行沙箱未接。",
        },
        selections,
    )


def build_mbpp(
    root: Path, out_dir: Path, *, per_category: int, seed: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """MBPP：没有官方类别，单组抽 5 条；判分要执行单测。"""
    path = root / "mbpp" / "mbpp.jsonl"
    rows = _read_rows(path)
    source_sha = _sha256(path)
    category = "function_generation"
    picked = sample_with_index(
        rows, per_category=per_category, seed=seed, category=f"mbpp:{category}"
    )
    picked_rows: list[dict[str, Any]] = []
    selections: list[dict[str, Any]] = []
    for index, item in picked:
        picked_rows.append({
            "benchmark": "MBPP",
            "category": category,
            "task_id": item.get("task_id"),
            "text": item.get("text"),
            "test_list": item.get("test_list"),
            "test_setup_code": item.get("test_setup_code"),
        })
        selections.append(select_row(
            benchmark="MBPP",
            category=category,
            source_path=path,
            source_index=index,
            source_row=item,
            seed=seed,
            per_category=per_category,
            source_sha=source_sha,
            source_size=len(rows),
        ))
    _write_jsonl(out_dir / "mbpp_5per_task.jsonl", picked_rows)
    return (
        {
            "file": "mbpp_5per_task.jsonl",
            "source": path.as_posix(),
            "source_file": path.name,
            "counts": {category: len(picked)},
            "source_sizes": {category: len(rows)},
            "source_sha256": {path.name: source_sha},
            "note": "无官方类别，单组 5 条；unit_test 判分，执行沙箱未接。",
        },
        selections,
    )


def _write_selection_record(
    out_dir: Path,
    selections: list[dict[str, Any]],
    *,
    seed: int,
    per_category: int,
    generated_at: str,
) -> None:
    """写 JSONL + 可读 Markdown 的抽样出处记录。"""
    _write_jsonl(out_dir / "selections.jsonl", selections)

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for item in selections:
        key = (item["benchmark"], item["category"], item["source_file"])
        grouped.setdefault(key, []).append(item)
    lines = [
        "# 分层抽样出处记录",
        "",
        f"- 生成时间：{generated_at}",
        f"- seed：{seed}；每类目标：{per_category} 条",
        "- 产物是平衡抽样，不是官方 benchmark 完整成绩。",
        "- 每条样本的源文件、源文件 hash、源行号、源 id 见 `selections.jsonl`。",
        "",
        "| benchmark | category | 源文件 | 源条数 | 选中 |",
        "|---|---|---|---:|---:|",
    ]
    for (benchmark, category, source_file), items in sorted(grouped.items()):
        source_size = items[0].get("source_size", "")
        lines.append(f"| {benchmark} | {category} | `{source_file}` | {source_size} | {len(items)} |")
    lines.append("")
    lines.append("> `source_index` 是源文件中的 0-based 行号；`source_sha256` 是源文件内容哈希前 16 位。")
    (out_dir / "selections.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def build_all(
    root: Path | str = DEFAULT_BENCH_ROOT,
    out_dir: Path | str = OUT_DIR,
    *,
    per_category: int = DEFAULT_PER_CATEGORY,
    seed: int = DEFAULT_SEED,
    sources: Iterable[str] | None = None,
) -> dict[str, Any]:
    root = Path(root)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    builders = {
        "bfcl": build_bfcl,
        "rgb": build_rgb,
        "tau2": build_tau2,
        "multihop": build_multihop,
        "cfbench": build_cfbench,
        "gaia": build_gaia,
        "humaneval": build_humaneval,
        "mbpp": build_mbpp,
        "swebench": build_swebench,
        "webarena": build_webarena,
        "osworld": build_osworld,
    }
    selected = list(builders) if sources is None else [name for name in sources if name in builders]
    unknown = [name for name in (sources or []) if name not in builders]
    if unknown:
        raise KeyError(f"未知抽样集合：{', '.join(unknown)}")
    sets: dict[str, Any] = {}
    selections: list[dict[str, Any]] = []
    for name in selected:
        info, picked = builders[name](root, out_dir, per_category=per_category, seed=seed)
        sets[name] = info
        selections.extend(picked)

    generated_at = datetime.now().isoformat(timespec="seconds")
    _write_selection_record(
        out_dir,
        selections,
        seed=seed,
        per_category=per_category,
        generated_at=generated_at,
    )
    manifest = {
        "generated_at": generated_at,
        "seed": seed,
        "per_category": per_category,
        "note": "平衡抽样，不是官方 benchmark 成绩；类别/源规模见 sets。",
        "selection_record": {
            "jsonl": "selections.jsonl",
            "markdown": "selections.md",
            "count": len(selections),
        },
        "sets": sets,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="按类别从公开 benchmark 源抽平衡样本")
    parser.add_argument("--root", default=str(DEFAULT_BENCH_ROOT))
    parser.add_argument("--out", default=str(OUT_DIR))
    parser.add_argument("--per-category", type=int, default=DEFAULT_PER_CATEGORY)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)
    manifest = build_all(
        args.root,
        args.out,
        per_category=args.per_category,
        seed=args.seed,
    )
    print(f"out: {Path(args.out).resolve()}")
    for name, info in manifest["sets"].items():
        total = sum(info["counts"].values())
        print(f"{name}: {total} rows / {len(info['counts'])} categories")
        print("  " + ", ".join(f"{key}={value}" for key, value in info["counts"].items()))
    print(f"selections: {manifest['selection_record']['count']} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
