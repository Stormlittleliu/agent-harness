# -*- coding: utf-8 -*-
"""系统提示词的分块组装。

- ``blocks``：块的读写与校验（`data/specs/<name>/prompt.yml`）；
- ``assemble``：按顺序 / 按真实状态拼接，带缓存与「用了哪些块」的报告。

用法见 ``docs/design/prompt-blocks.md``。
"""
from core.prompts.assemble import (
    Assembly,
    PromptContext,
    assemble,
    context_from_scenario,
    get_assembled,
    render,
)
from core.prompts.blocks import (
    PromptBlock,
    PromptBook,
    load_book,
    save_book,
    validate_book,
)

__all__ = [
    "Assembly",
    "PromptBlock",
    "PromptBook",
    "PromptContext",
    "assemble",
    "context_from_scenario",
    "get_assembled",
    "load_book",
    "render",
    "save_book",
    "validate_book",
]
