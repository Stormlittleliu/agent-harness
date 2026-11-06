# -*- coding: utf-8 -*-
"""路径层：数据根可外置，数据集解析优先外置、回退旧布局。"""
from pathlib import Path

from core import paths


def test_data_and_spec_roots_are_absolute():
    assert paths.PROJECT_ROOT.is_absolute()
    assert paths.DATA_ROOT.is_absolute()
    assert paths.SPEC_ROOT.is_absolute()


def test_resolve_data_path_maps_runtime_and_data():
    assert paths.resolve_data_path("data/knowledge") == paths.DATA_ROOT / "knowledge"
    assert paths.resolve_data_path("data/runtime/x.sqlite") == paths.RUNTIME_ROOT / "x.sqlite"
    absolute = Path("C:/tmp/example.sqlite") if Path("C:/").exists() else Path("/tmp/example.sqlite")
    assert paths.resolve_data_path(absolute) == absolute


def test_get_abs_path_honors_runtime_and_spec_roots():
    from core.utils.path_tool import get_abs_path

    assert get_abs_path("data/runtime/x.sqlite") == str(paths.RUNTIME_ROOT / "x.sqlite")
    assert get_abs_path("data/specs/abc") == str(paths.SPEC_ROOT / "abc")


def test_dataset_path_prefers_external_then_legacy(monkeypatch, tmp_path):
    external = tmp_path / "external"
    legacy = tmp_path / "legacy"
    (legacy / "public").mkdir(parents=True)
    (legacy / "public" / "sample.jsonl").write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(paths, "DATASET_ROOT", external)
    monkeypatch.setattr(paths, "LEGACY_DATASET_ROOTS", (legacy,))

    assert paths.dataset_path("public", "sample.jsonl") == legacy / "public" / "sample.jsonl"
    assert paths.dataset_path("public", "missing.jsonl") == external / "public" / "missing.jsonl"


def test_benchmark_root_has_no_absolute_author_path():
    assert r"E:\CODE\benchmarks" not in str(paths.BENCHMARK_ROOT)
