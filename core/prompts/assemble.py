# -*- coding: utf-8 -*-
"""把块拼成 system prompt：按顺序、按状态、带缓存。

三段式：

1. ``PromptContext`` 只装**真实状态**（有哪些工具、有没有工作流、是不是路由场景、
   有没有记忆文件…），不是从消息里搜出来的；
2. ``assemble`` 按 spec 给的块顺序拼接，跳过 ``when`` 不满足的块，做 ``{var}`` 插值；
3. ``get_assembled`` 用 json 作为缓存键——上下文没变就不重复拼接。

为什么不缓存（而是每次拼）：拼接本身很便宜，真正贵的是 token；这里缓存只为省重复
字符串处理，不做跨请求的 prompt cache（那是模型侧的事）。
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from typing import Any

from core.prompts.blocks import PromptBlock, PromptBook

PLACEHOLDER = re.compile(r"\{([a-z_][\w]*)\}")


@dataclass(frozen=True)
class PromptContext:
    """拼提示词时能看到的状态；只放事实，不放猜测。"""

    name: str = ""
    kind: str = "agent"
    tools: tuple[str, ...] = ()
    workflows: tuple[str, ...] = ()
    workspace: str = ""
    memory: str = ""
    has_cases: bool = False
    today: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def values(self) -> dict[str, str]:
        data = {
            "name": self.name,
            "kind": self.kind,
            "tools": "、".join(self.tools) if self.tools else "（无）",
            "tool_count": str(len(self.tools)),
            "workflows": "、".join(self.workflows) if self.workflows else "（无）",
            "workspace": self.workspace or "（未指定）",
            "memory": self.memory or "（无）",
            "today": self.today or date.today().isoformat(),
        }
        data.update({str(key): str(value) for key, value in self.extra.items()})
        return data


@dataclass(frozen=True)
class Assembly:
    """拼接结果 + 用了哪些块（界面与排查都用得上）。"""

    text: str
    sections: tuple[tuple[str, str], ...] = ()

    @property
    def block_ids(self) -> list[str]:
        return [block_id for block_id, _ in self.sections]

    def report(self) -> str:
        """一行摘要：``identity · rules_tools · rules_safety``。"""
        return " · ".join(block_id for block_id, _ in self.sections) or "（没有块）"


def render(body: str, context: PromptContext) -> str:
    """把块里的 ``{name} {tools} {today}`` 换成真实值；未知占位符原样保留。"""
    values = context.values()

    def _replace(match: re.Match) -> str:
        key = match.group(1)
        return values.get(key, match.group(0))

    return PLACEHOLDER.sub(_replace, body or "")


def assemble(
    block_ids: list[str],
    book: PromptBook,
    context: PromptContext,
    overrides: dict[str, str] | None = None,
) -> Assembly:
    """按顺序拼块：跳过条件不满足的、套用覆盖文本、去掉空块。"""
    overrides = overrides or {}
    parts: list[str] = []
    sections: list[tuple[str, str]] = []
    for block_id in block_ids:
        block: PromptBlock | None = book.get(str(block_id))
        if block is None or not block.enabled(context):
            continue
        body = overrides.get(block.id, block.body)
        text = render(body, context).strip()
        if not text:
            continue
        parts.append(text)
        sections.append((block.id, block.title))
    return Assembly(text="\n\n".join(parts), sections=tuple(sections))


@lru_cache(maxsize=128)
def _cached(key: str, block_ids: tuple[str, ...], context_json: str, overrides_json: str) -> str:
    """真正的拼接入口（被 lru_cache 包住）；参数都是可哈希的字符串。"""
    from core.prompts.blocks import PromptBlock as _Block  # 避免循环 import
    from core.prompts.blocks import PromptBook as _Book

    book_data = json.loads(key)
    book = _Book(
        blocks={
            block_id: _Block(
                id=block_id,
                title=value["title"],
                body=value["body"],
                when=value.get("when", "always"),
            )
            for block_id, value in book_data.items()
        },
        order=tuple(block_ids),
    )
    context_data = json.loads(context_json)
    context = PromptContext(
        name=context_data.get("name", ""),
        kind=context_data.get("kind", "agent"),
        tools=tuple(context_data.get("tools") or ()),
        workflows=tuple(context_data.get("workflows") or ()),
        workspace=context_data.get("workspace", ""),
        memory=context_data.get("memory", ""),
        has_cases=bool(context_data.get("has_cases")),
        today=context_data.get("today", ""),
        extra=context_data.get("extra") or {},
    )
    return assemble(
        list(block_ids),
        book,
        context,
        json.loads(overrides_json),
    ).text


def get_assembled(
    block_ids: list[str],
    book: PromptBook,
    context: PromptContext,
    overrides: dict[str, str] | None = None,
) -> str:
    """带缓存的拼接：同一套块 + 同一份状态只拼一次。"""
    key = json.dumps(
        {
            block_id: {
                "title": book.blocks[block_id].title,
                "body": book.blocks[block_id].body,
                "when": book.blocks[block_id].when,
            }
            for block_id in book.ids()
            if block_id in book.blocks
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    context_json = json.dumps(
        {
            "name": context.name,
            "kind": context.kind,
            "tools": list(context.tools),
            "workflows": list(context.workflows),
            "workspace": context.workspace,
            "memory": context.memory,
            "has_cases": context.has_cases,
            "today": context.today,
            "extra": context.extra,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return _cached(
        key,
        tuple(str(item) for item in block_ids),
        context_json,
        json.dumps(overrides or {}, ensure_ascii=False, sort_keys=True),
    )


def context_from_scenario(scenario: Any, **extra: Any) -> PromptContext:
    """从已构建的 ``Scenario`` 取真实状态，供拼接用。"""
    tools = tuple(str(getattr(tool, "name", "")) for tool in getattr(scenario, "tools", []) or [])
    workflows: tuple[str, ...] = ()
    factory = getattr(scenario, "workflow_factory", None)
    if callable(factory):
        try:
            workflows = tuple(str(name) for name in factory(scenario))
        except Exception:  # noqa: BLE001 - 工作流构建失败不该挡住提示词
            workflows = ()
    return PromptContext(
        name=str(getattr(scenario, "name", "")),
        kind=str(getattr(scenario, "kind", "agent")),
        tools=tools,
        workflows=workflows,
        workspace=str(extra.pop("workspace", "")),
        memory=str(extra.pop("memory", "")),
        has_cases=bool(getattr(scenario, "cases_path", None)),
        extra=extra,
    )
