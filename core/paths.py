# -*- coding: utf-8 -*-
"""项目路径的唯一入口：代码、数据、运行时、数据集、公开 benchmark 源。

这里解决两个老问题：

1. 以前 ``data/...`` 散落在十几个模块里，换机器/换数据盘只能改代码；
2. benchmark 源路径曾默认写死 ``E:\\CODE\\benchmarks``，仓库不可移植。

约定：

- ``AH_DATA_ROOT``：所有项目数据的根，默认 ``<repo>/data``；
- ``AH_RUNTIME_ROOT``：可写运行时数据，默认 ``<data>/runtime``；
- ``AH_SPEC_ROOT``：场景 spec 根，默认 ``<data>/specs``；
- ``AH_DATASET_ROOT``：外置数据集根，默认 ``<data>/datasets``；
- ``AH_BENCHMARK_ROOT``：公开 benchmark 原始数据根，无默认绝对路径；
  未设置时指向 ``<repo>/benchmark_sources``（空目录 + README，仓库自包含）。

仓库只保留数据集引用与目录；``data/datasets`` 的内容由本地导入/采样生成，
不进 git。旧的 ``data/evals/datasets`` 继续作为只读回退路径，保证已有环境可用。
"""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


DATA_ROOT = _env_path("AH_DATA_ROOT", PROJECT_ROOT / "data")
RUNTIME_ROOT = _env_path("AH_RUNTIME_ROOT", DATA_ROOT / "runtime")
SPEC_ROOT = _env_path("AH_SPEC_ROOT", DATA_ROOT / "specs")
DATASET_ROOT = _env_path("AH_DATASET_ROOT", DATA_ROOT / "datasets")
EVALS_ROOT = DATA_ROOT / "evals"
EVALS_DATASETS_ROOT = EVALS_ROOT / "datasets"
KNOWLEDGE_ROOT = DATA_ROOT / "knowledge"

# 旧布局只读回退；新数据一律优先落在 DATASET_ROOT。
LEGACY_DATASET_ROOTS = (EVALS_DATASETS_ROOT,)

BENCHMARK_ROOT = _env_path("AH_BENCHMARK_ROOT", PROJECT_ROOT / "benchmark_sources")
if not os.environ.get("AH_BENCHMARK_ROOT") and os.environ.get("BENCHMARK_ROOT"):
    BENCHMARK_ROOT = _env_path("BENCHMARK_ROOT", PROJECT_ROOT / "benchmark_sources")


class DatasetNotInstalled(FileNotFoundError):
    """数据集 / benchmark 源未安装；CLI 捕获后打印提示，而不是抛 traceback。"""


def dataset_missing_message(path: Path | str) -> str:
    return (
        f"未安装数据集：{path}\n"
        f"请把数据放到外置根 {DATASET_ROOT}（可用 AH_DATASET_ROOT 覆盖），"
        "或运行 `python -m dataset_ops.stratified --per-category 5 --seed 42` 重新生成；"
        "详见 data/datasets/README.md。"
    )


def benchmark_missing_message(path: Path | str) -> str:
    return (
        f"未安装 benchmark 源：{path}\n"
        f"请设置 AH_BENCHMARK_ROOT（默认 {BENCHMARK_ROOT}）指向本地 benchmark 仓库，"
        "再运行 `python -m core.benchmarks.catalog --list` 检查；"
        "详见 benchmark_sources/README.md。"
    )


def repo_path(*parts: str) -> Path:
    return PROJECT_ROOT.joinpath(*parts)


def resolve_data_path(path: str | Path) -> Path:
    """把 ``data/...`` 相对路径解析到 DATA_ROOT；绝对路径原样返回。"""
    value = Path(path)
    if value.is_absolute():
        return value
    normalized = value.as_posix()
    if normalized == "data":
        return DATA_ROOT
    if normalized.startswith("data/runtime/"):
        return RUNTIME_ROOT / normalized[len("data/runtime/"):]
    if normalized.startswith("data/specs/"):
        return SPEC_ROOT / normalized[len("data/specs/"):]
    if normalized.startswith("data/"):
        return DATA_ROOT / normalized[5:]
    return PROJECT_ROOT / value


def data_path(*parts: str) -> Path:
    return DATA_ROOT.joinpath(*parts)


def runtime_path(*parts: str) -> Path:
    return RUNTIME_ROOT.joinpath(*parts)


def spec_path(name: str = "") -> Path:
    return SPEC_ROOT / name if name else SPEC_ROOT


def dataset_path(*parts: str) -> Path:
    """解析数据集路径：外置根优先，旧仓库布局次之。

    返回可能不存在的首选路径；调用方用 ``exists()`` 判断是否已导入。
    """
    relative = Path(*parts)
    if relative.is_absolute():
        return relative
    for root in (DATASET_ROOT, *LEGACY_DATASET_ROOTS):
        candidate = root / relative
        if candidate.exists():
            return candidate
    return DATASET_ROOT / relative


def dataset_candidates(*parts: str) -> list[Path]:
    relative = Path(*parts)
    if relative.is_absolute():
        return [relative]
    return [root / relative for root in (DATASET_ROOT, *LEGACY_DATASET_ROOTS)]


def benchmark_path(*parts: str) -> Path:
    """解析公开 benchmark 原始数据路径（``AH_BENCHMARK_ROOT`` / benchmark_sources）。"""
    return BENCHMARK_ROOT.joinpath(*parts)


def benchmark_catalog_root() -> Path:
    """样例 catalog 的输出根：外置优先，旧 ``data/benchmarks`` 回退。"""
    for root in (DATASET_ROOT / "benchmarks", DATA_ROOT / "benchmarks"):
        if (root / "manifest.json").exists() or (root / "catalog.jsonl").exists():
            return root
    return DATASET_ROOT / "benchmarks"


def benchmark_catalog_manifest() -> Path:
    """catalog manifest：外置优先；旧 ``data/benchmarks/manifest.json`` 只读回退。

    catalog 正文可以移到外置数据根，但 manifest 作为仓库内的来源引用保留，
    所以这里单独解析，避免 dashboard 同时找不到两者。
    """
    for root in (DATASET_ROOT / "benchmarks", DATA_ROOT / "benchmarks"):
        candidate = root / "manifest.json"
        if candidate.is_file():
            return candidate
    return DATA_ROOT / "benchmarks" / "manifest.json"
