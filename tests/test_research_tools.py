# -*- coding: utf-8 -*-
import json
from pathlib import Path

from core.scenarios.research_assistant.tools import SourceStore


def _json(result: str) -> dict:
    return json.loads(result)


def test_source_store_list_search_read_and_report(tmp_path: Path):
    sources = tmp_path / "sources"
    reports = tmp_path / "reports"
    sources.mkdir()
    (sources / "source_a.md").write_text(
        "# 资料 A\n\nAgent 评测要基于 outcome。\n", encoding="utf-8"
    )
    (sources / "source_b.md").write_text(
        "# 资料 B\n\n评测要跑 5 trials 和 pass^k。\n", encoding="utf-8"
    )
    store = SourceStore(sources, reports)

    listing = _json(store.list_sources())
    assert {item["id"] for item in listing["sources"]} == {"source_a", "source_b"}

    found = _json(store.search_sources("outcome"))
    assert found["results"][0]["id"] == "source_a"

    read = _json(store.read_source("source_b"))
    assert read["ok"] is True
    assert "pass^k" in read["content"]

    report = _json(store.write_report("对比报告", "# 结论\n\nA 与 B 一致。"))
    assert report["ok"] is True
    assert Path(report["path"]).exists()
