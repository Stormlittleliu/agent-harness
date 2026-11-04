# -*- coding: utf-8 -*-
"""系统提示词的"块"：一个个可独立维护的小段，最后拼接成最终 prompt。

为什么拆：一整段 system prompt 里混着身份、工具规则、引用规则、语气、安全边界，
改一条不知道会不会碰坏另一条；换场景时又整段重写。拆成块之后：

- 每块独立维护、独立审阅，改「引用规则」不会动「身份」；
- 块可以按**真实状态**决定是否加载（有没有工具、有没有工作流、是不是路由场景），
  不是靠消息里的关键词猜；
- 拼接结果可缓存：同一份结构 + 同一份状态，不重复拼。

块本身是数据（`data/specs/<name>/prompt.yml`），不写代码。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# 块里可以用的状态条件：只认真实状态，不做关键词猜测。
WHEN_FLAGS = (
    "always",
    "has_tools",
    "no_tools",
    "has_workflow",
    "no_workflow",
    "kind:router",
    "kind:agent",
    "has_memory",
    "has_cases",
)


@dataclass(frozen=True)
class PromptBlock:
    """一个可复用的提示词段落。"""

    id: str
    title: str
    body: str
    when: str = "always"

    def enabled(self, context: Any) -> bool:
        """按真实状态判断这一段要不要加载。"""
        flag = (self.when or "always").strip()
        if flag in ("", "always"):
            return True
        if flag == "has_tools":
            return bool(context.tools)
        if flag == "no_tools":
            return not context.tools
        if flag == "has_workflow":
            return bool(context.workflows)
        if flag == "no_workflow":
            return not context.workflows
        if flag == "kind:router":
            return str(context.kind) == "router"
        if flag == "kind:agent":
            return str(context.kind) == "agent"
        if flag == "has_memory":
            return bool(context.memory)
        if flag == "has_cases":
            return bool(context.has_cases)
        return True  # 未知条件不静默吞掉整段，宁可多加载


@dataclass(frozen=True)
class PromptBook:
    """一个场景的块集合（顺序由 ``order`` 决定，缺省按文件里的顺序）。"""

    blocks: dict[str, PromptBlock] = field(default_factory=dict)
    order: tuple[str, ...] = ()

    def ids(self) -> list[str]:
        return list(self.order) or list(self.blocks)

    def get(self, block_id: str) -> PromptBlock | None:
        return self.blocks.get(block_id)


def load_book(path: Path | str) -> PromptBook:
    """读 ``prompt.yml``：``blocks: {id: {title, body, when}}`` + 可选 ``order``。"""
    target = Path(path)
    if not target.is_file():
        return PromptBook()
    data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    raw = data.get("blocks") or {}
    blocks: dict[str, PromptBlock] = {}
    for block_id, value in raw.items():
        if isinstance(value, str):
            blocks[str(block_id)] = PromptBlock(str(block_id), str(block_id), value)
            continue
        if not isinstance(value, dict):
            continue
        blocks[str(block_id)] = PromptBlock(
            id=str(block_id),
            title=str(value.get("title") or block_id),
            body=str(value.get("body") or ""),
            when=str(value.get("when") or "always"),
        )
    order = tuple(str(item) for item in (data.get("order") or []) if str(item) in blocks)
    return PromptBook(blocks=blocks, order=order)


def save_book(path: Path | str, book: PromptBook) -> Path:
    """把块写回 ``prompt.yml``（顺序写进 ``order``，读的时候同序拼接）。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "order": list(book.ids()),
        "blocks": {
            block_id: {
                "title": book.blocks[block_id].title,
                "body": book.blocks[block_id].body,
                **({"when": book.blocks[block_id].when} if book.blocks[block_id].when != "always" else {}),
            }
            for block_id in book.ids()
        },
    }
    target.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
        newline="\n",
    )
    return target


def validate_book(ids: list[str], book: PromptBook) -> list[str]:
    """校验 spec 里引用的块都存在、且没有重复。"""
    errors: list[str] = []
    seen: set[str] = set()
    for block_id in ids:
        name = str(block_id).strip()
        if not name:
            errors.append("prompt.blocks 里有空块名")
            continue
        if name in seen:
            errors.append(f"prompt.blocks 重复引用了块：{name}")
        seen.add(name)
        if book.get(name) is None:
            errors.append(
                f"prompt.blocks 引用了不存在的块：{name}"
                f"（可用：{', '.join(book.ids()) or '（空）'}）"
            )
    return errors
