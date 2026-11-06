# -*- coding: utf-8 -*-
"""办公 / 学习助手工具：笔记检索、笔记写入、长期偏好、翻译与总结。"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool


def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _slugify(title: str) -> str:
    slug = re.sub(r"[^\w一-鿿-]+", "_", (title or "").strip()).strip("_")
    return (slug or f"note_{datetime.now():%Y%m%d_%H%M%S}")[:60]


def _title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("# ").strip() or fallback
    return fallback


class NoteStore:
    """两段式笔记库：seed 只读，user 可写。"""

    def __init__(self, seed_dir: Path | str, user_dir: Path | str):
        self.seed_dir = Path(seed_dir)
        self.user_dir = Path(user_dir)
        self.seed_dir.mkdir(parents=True, exist_ok=True)
        self.user_dir.mkdir(parents=True, exist_ok=True)

    def _entries(self):
        for source, root in (("seed", self.seed_dir), ("user", self.user_dir)):
            for path in sorted(root.rglob("*.md")):
                relative = path.relative_to(root).with_suffix("").as_posix()
                yield f"{source}/{relative}", source, path

    def _find(self, note_id: str) -> tuple[str, str, Path] | None:
        for current_id, source, path in self._entries():
            if current_id == note_id or path.stem == note_id:
                return current_id, source, path
        return None

    def list_notes(self) -> str:
        notes = []
        for note_id, source, path in self._entries():
            content = path.read_text(encoding="utf-8", errors="replace")
            notes.append({
                "id": note_id,
                "title": _title(content, path.stem),
                "source": source,
            })
        return _json({"notes": notes})

    def read_note(self, note_id: str) -> str:
        found = self._find(note_id)
        if found is None:
            return _json({"ok": False, "error": f"笔记不存在：{note_id}"})
        current_id, source, path = found
        content = path.read_text(encoding="utf-8", errors="replace")
        return _json({
            "ok": True,
            "id": current_id,
            "title": _title(content, path.stem),
            "source": source,
            "content": content[:8000],
        })

    @staticmethod
    def _terms(query: str) -> list[str]:
        try:
            import jieba  # type: ignore

            terms = [term.strip().lower() for term in jieba.lcut(query or "") if len(term.strip()) > 1]
        except Exception:  # noqa: BLE001
            terms = re.findall(r"[a-zA-Z0-9_]{2,}|[一-鿿]{2,}", (query or "").lower())
        return list(dict.fromkeys(term for term in terms if term)) or [(query or "").lower()]

    def search_notes(self, query: str, limit: int = 5) -> str:
        terms = self._terms(query)
        limit = max(1, min(int(limit or 5), 20))
        results = []
        for note_id, source, path in self._entries():
            content = path.read_text(encoding="utf-8", errors="replace")
            lower = content.lower()
            title = _title(content, path.stem)
            score = sum(lower.count(term) for term in terms)
            score += sum(2 for term in terms if term in title.lower())
            if score <= 0:
                continue
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            scored_lines = []
            for line in lines:
                line_score = sum(line.lower().count(term) for term in terms)
                if line_score:
                    scored_lines.append((line_score, line))
            scored_lines.sort(key=lambda pair: -pair[0])
            if scored_lines:
                snippet = " … ".join(line for _, line in scored_lines[:3])
            else:
                snippet = " ".join(lines[:3])
            results.append({
                "id": note_id,
                "title": title,
                "source": source,
                "score": score,
                "snippet": snippet[:400],
            })
        results.sort(key=lambda item: (-item["score"], item["id"]))
        return _json({"query": query, "results": results[:limit]})

    def write_note(self, title: str, content: str) -> str:
        stem = _slugify(title)
        path = self.user_dir / f"{stem}.md"
        index = 2
        while path.exists():
            path = self.user_dir / f"{stem}_{index}.md"
            index += 1
        path.write_text(content, encoding="utf-8")
        return _json({
            "ok": True,
            "id": f"user/{path.stem}",
            "path": str(path),
            "title": title,
        })


class MemoryStore:
    """SQLite 长期偏好；key -> value。"""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS memory ("
                "key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)"
            )

    def _connect(self):
        return sqlite3.connect(str(self.path))

    def remember(self, key: str, value: str) -> str:
        key = (key or "").strip()
        value = (value or "").strip()
        if not key or not value:
            return _json({"ok": False, "error": "key 和 value 都不能为空"})
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO memory (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (key, value, now),
            )
        return _json({"ok": True, "key": key, "value": value, "updated_at": now})

    def recall(self, key: str) -> str:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT key, value, updated_at FROM memory WHERE key = ?", ((key or "").strip(),)
            ).fetchone()
        if row is None:
            return _json({"ok": False, "key": key, "error": "没有找到这条记忆"})
        return _json({"ok": True, "key": row[0], "value": row[1], "updated_at": row[2]})

    def list_memory(self) -> str:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT key, value, updated_at FROM memory ORDER BY updated_at DESC"
            ).fetchall()
        return _json({
            "ok": True,
            "items": [{"key": row[0], "value": row[1], "updated_at": row[2]} for row in rows],
        })


@lru_cache(maxsize=1)
def _translate_chain():
    """模型链延迟到真正调用翻译时才构造，目录/场景发现不应要求 API key。"""
    from core.llm.factory import chat_model

    return (
        PromptTemplate.from_template(
            "把下面的文本翻译成 {target_language}。只输出译文，不要解释：\n\n{text}"
        )
        | chat_model
        | StrOutputParser()
    )


@lru_cache(maxsize=1)
def _summarize_chain():
    from core.llm.factory import chat_model

    return (
        PromptTemplate.from_template(
            "把下面的材料整理成{style}，保留关键事实和数字：\n\n{text}"
        )
        | chat_model
        | StrOutputParser()
    )


def build_workspace_tools(store: NoteStore, memory: MemoryStore):
    @tool("list_notes", description="列出当前可用的 seed / user 笔记，返回 id、标题和来源。")
    def list_notes() -> str:
        return store.list_notes()

    @tool("read_note", description="按 id 读取一篇笔记的完整内容，返回标题、来源和正文。")
    def read_note(note_id: str) -> str:
        return store.read_note(note_id)

    @tool(
        "search_notes",
        description="按关键词搜索笔记，返回最相关的笔记 id、标题、来源和片段；回答前优先调用。",
    )
    def search_notes(query: str, limit: int = 5) -> str:
        return store.search_notes(query, limit)

    @tool(
        "write_note",
        description="把新笔记写入 user 笔记库；标题用于生成文件名，正文为 Markdown。",
    )
    def write_note(title: str, content: str) -> str:
        return store.write_note(title, content)

    @tool("remember", description="记住一条用户偏好或事实，key/value 都是字符串。")
    def remember(key: str, value: str) -> str:
        return memory.remember(key, value)

    @tool("recall", description="按 key 取回之前记住的偏好或事实。")
    def recall(key: str) -> str:
        return memory.recall(key)

    @tool("list_memory", description="列出所有长期记忆，用于了解用户偏好。")
    def list_memory() -> str:
        return memory.list_memory()

    @tool("translate", description="把文本翻译成目标语言；只返回译文。")
    def translate(text: str, target_language: str = "中文") -> str:
        return _translate_chain().invoke({"text": text, "target_language": target_language})

    @tool("summarize", description="把材料总结成要点、学习笔记或简短摘要。")
    def summarize(text: str, style: str = "要点") -> str:
        return _summarize_chain().invoke({"text": text, "style": style})

    return [
        list_notes,
        read_note,
        search_notes,
        write_note,
        remember,
        recall,
        list_memory,
        translate,
        summarize,
    ]
