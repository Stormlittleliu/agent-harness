# -*- coding: utf-8 -*-
"""统一 benchmark 样例集：加载各适配器 → 分层抽样 → 输出 catalog。

用法：
    python -m core.benchmarks.catalog --list
    python -m core.benchmarks.catalog --build --per-source 12 --seed 42
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from core.benchmarks.adapters import ADAPTERS
from core.benchmarks.paths import CATALOG_OUT
from core.benchmarks.sampling import stratified_sample
from core.benchmarks.schema import BenchTask

try:
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def _summary(tasks: list[BenchTask]) -> dict:
    return {
        "by_source": dict(Counter(task.source for task in tasks)),
        "by_category": dict(Counter(task.category for task in tasks)),
        "by_task_type": dict(Counter(task.task_type for task in tasks)),
        "by_bucket": dict(Counter(task.bucket for task in tasks)),
        "by_grader": dict(Counter(task.grader for task in tasks)),
        "by_environment": dict(Counter(task.environment.get("kind", "unknown") for task in tasks)),
    }


def list_adapters() -> None:
    print(f"{'adapter':<16} {'available':<10} {'loaded':>7}  note")
    for adapter in ADAPTERS:
        tasks = adapter.load() if adapter.available() else []
        flag = "yes" if adapter.available() else "no"
        print(f"{adapter.name:<16} {flag:<10} {len(tasks):>7}  {adapter.note()}")
        if not adapter.available():
            print(f"{'':<16} download: {adapter.url}")


def build(per_source: int, seed: int, out_dir: Path, only: str | None = None) -> None:
    adapters = [adapter for adapter in ADAPTERS if only is None or adapter.name == only]
    loaded: list[BenchTask] = []
    source_rows = []
    for adapter in adapters:
        tasks = adapter.load() if adapter.available() else []
        loaded.extend(tasks)
        source_rows.append({
            "name": adapter.name,
            "available": adapter.available(),
            "version": adapter.version(),
            "license": adapter.license,
            "url": adapter.url,
            "loaded": len(tasks),
            "note": adapter.note(),
        })
        print(f"[load] {adapter.name}: {len(tasks)} tasks")

    sampled = stratified_sample(loaded, per_source=per_source, seed=seed)
    summary = _summary(sampled)
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "seed": seed,
        "per_source": per_source,
        "total": len(sampled),
        "sources": [
            {
                **row,
                "sampled": sum(1 for task in sampled if task.source == row["name"]),
            }
            for row in source_rows
        ],
        "summary": summary,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "catalog.jsonl"
    manifest_path = out_dir / "manifest.json"
    md_path = out_dir / "catalog.md"

    jsonl_path.write_text(
        "\n".join(json.dumps(task.to_dict(), ensure_ascii=False) for task in sampled) + "\n",
        encoding="utf-8",
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 统一 benchmark 样例集",
        "",
        f"- 生成时间：{manifest['generated_at']}",
        f"- 抽样：每个来源 {per_source} 条，seed={seed}",
        f"- 总计：{len(sampled)} 条",
        "",
        "## 来源",
        "",
        "| 来源 | 可用 | 版本 | 原始条数 | 抽样 | 许可 |",
        "|:---|:---:|:---|:---:|:---:|:---|",
    ]
    for row in manifest["sources"]:
        lines.append(
            f"| {row['name']} | {'✅' if row['available'] else '❌'} | {row['version']} | "
            f"{row['loaded']} | {row['sampled']} | {row['license']} |"
        )
    lines += ["", "## 分类", ""]
    for name, count in sorted(summary["by_category"].items()):
        lines.append(f"- {name}: {count}")
    lines += ["", "## AgentGuide Bucket", ""]
    for name, count in sorted(summary["by_bucket"].items()):
        lines.append(f"- {name}: {count}")
    lines += ["", "## 样例", "", "| ID | 来源 | Bucket | 类别 | 任务 | 评分 |", "|:---|:---|:---|:---|:---|:---|"]
    for task in sampled:
        instruction = task.instruction.replace("\n", " ")[:60]
        lines.append(
            f"| {task.id} | {task.source} | {task.bucket} | {task.category} | {instruction} | {task.grader} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n=== summary ===")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\ncatalog: {jsonl_path}")
    print(f"manifest: {manifest_path}")
    print(f"report: {md_path}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="统一 benchmark 样例集")
    parser.add_argument("--list", action="store_true", help="列出适配器与可用性")
    parser.add_argument("--build", action="store_true", help="构建 catalog")
    parser.add_argument("--per-source", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--source", default=None, help="只构建某个适配器")
    parser.add_argument("--out", default=str(CATALOG_OUT))
    args = parser.parse_args(argv)

    if args.list:
        list_adapters()
        return
    if args.build:
        build(args.per_source, args.seed, Path(args.out), only=args.source)
        return
    parser.print_help()


if __name__ == "__main__":
    main()
