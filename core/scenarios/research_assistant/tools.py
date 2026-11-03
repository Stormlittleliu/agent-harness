# -*- coding: utf-8 -*-
"""研究助手工具：资料列表、读取、搜索与报告写入。"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


class SourceStore:
    def __init__(self, source_dir: Path | str, report_dir: Path | str):
        self.source_dir = Path(source_dir)
        self.report_dir = Path(report_dir)
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def _sources(self):
        for path in sorted(self.source_dir.rglob("*.md")):
            yield path.relative_to(self.source_dir).with_suffix("").as_posix(), path

    def list_sources(self) -> str:
        items = []
        for source_id, path in self._sources():
            content = path.read_text(encoding="utf-8", errors="replace")
            title = next(
                (line.lstrip("# ").strip() for line in content.splitlines() if line.startswith("#")),
                path.stem,
            )
            items.append({"id": source_id, "title": title, "path": path.name})
        return _json({"sources": items})

    def read_source(self, source_id: str) -> str:
        for current_id, path in self._sources():
            if current_id == source_id or path.stem == source_id:
                return _json({
                    "ok": True,
                    "id": current_id,
                    "title": path.stem,
                    "content": path.read_text(encoding="utf-8", errors="replace")[:8000],
                })
        return _json({"ok": False, "error": f"资料不存在：{source_id}"})

    @staticmethod
    def _terms(query: str) -> list[str]:
        try:
            import jieba  # type: ignore

            terms = [term.strip().lower() for term in jieba.lcut(query or "") if len(term.strip()) > 1]
        except Exception:  # noqa: BLE001
            terms = re.findall(r"[a-zA-Z0-9_]{2,}|[一-鿿]{2,}", (query or "").lower())
        return list(dict.fromkeys(term for term in terms if term)) or [(query or "").lower()]

    def search_sources(self, query: str, limit: int = 5) -> str:
        terms = self._terms(query)
        limit = max(1, min(int(limit or 5), 20))
        results = []
        for source_id, path in self._sources():
            content = path.read_text(encoding="utf-8", errors="replace")
            lower = content.lower()
            score = sum(lower.count(term) for term in terms)
            if score <= 0:
                continue
            snippet = ""
            for line in content.splitlines():
                if any(term in line.lower() for term in terms):
                    snippet = line.strip()[:240]
                    break
            results.append({
                "id": source_id,
                "title": path.stem,
                "score": score,
                "snippet": snippet or content[:240].replace("\n", " "),
            })
        results.sort(key=lambda item: (-item["score"], item["id"]))
        return _json({"query": query, "results": results[:limit]})

    def write_report(self, title: str, content: str) -> str:
        slug = re.sub(r"[^\w一-鿿-]+", "_", title or "report").strip("_") or "report"
        path = self.report_dir / f"{slug}_{datetime.now():%Y%m%d_%H%M%S}.md"
        path.write_text(content, encoding="utf-8")
        return _json({"ok": True, "path": str(path), "bytes": len(content.encode("utf-8"))})


def build_research_tools(store: SourceStore):
    @tool("list_sources", description="列出当前研究资料，返回 id 和标题。")
    def list_sources() -> str:
        return store.list_sources()

    @tool("read_source", description="按 id 读取一份资料的完整文本。")
    def read_source(source_id: str) -> str:
        return store.read_source(source_id)

    @tool("search_sources", description="按关键词搜索研究资料，返回 id、标题和片段。")
    def search_sources(query: str, limit: int = 5) -> str:
        return store.search_sources(query, limit)

    @tool("write_report", description="把研究报告写入报告目录，返回保存路径。")
    def write_report(title: str, content: str) -> str:
        return store.write_report(title, content)

    return [list_sources, read_source, search_sources, write_report]
