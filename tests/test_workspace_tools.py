# -*- coding: utf-8 -*-
import json
from pathlib import Path

from core.scenarios.workspace_assistant.tools import MemoryStore, NoteStore


def _json(result: str) -> dict:
    return json.loads(result)


def test_note_store_search_read_write(tmp_path: Path):
    seed = tmp_path / "seed"
    user = tmp_path / "user"
    seed.mkdir()
    (seed / "agent.md").write_text(
        "# Agent 笔记\n\n评测要看 pass^k、成本和时延。\n", encoding="utf-8"
    )
    store = NoteStore(seed, user)

    listing = _json(store.list_notes())
    assert listing["notes"][0]["id"] == "seed/agent"

    found = _json(store.search_notes("评测 成本"))
    assert found["results"]
    assert found["results"][0]["id"] == "seed/agent"

    read = _json(store.read_note("seed/agent"))
    assert read["ok"] is True
    assert "pass^k" in read["content"]

    written = _json(store.write_note("我的笔记", "记住 outcome。"))
    assert written["ok"] is True
    assert (user / "我的笔记.md").exists()
    assert _json(store.read_note(written["id"]))["content"] == "记住 outcome。"


def test_memory_store_upsert_and_recall(tmp_path: Path):
    memory = MemoryStore(tmp_path / "memory.sqlite")
    assert _json(memory.remember("style", "简洁"))["ok"] is True
    assert _json(memory.remember("style", "要点式"))["ok"] is True
    recalled = _json(memory.recall("style"))
    assert recalled["ok"] is True
    assert recalled["value"] == "要点式"
    listing = _json(memory.list_memory())
    assert listing["items"][0]["key"] == "style"
    assert _json(memory.recall("missing"))["ok"] is False
