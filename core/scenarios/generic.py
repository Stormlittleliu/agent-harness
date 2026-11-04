# -*- coding: utf-8 -*-
"""通用 spec 场景：不写代码，只靠 ``data/specs/<name>/`` 也能构建出可跑的场景。

边界（刻意的，别绕开）：

- 工具只来自**固定池**（办公 / 笔记那一套），不做"spec 里随便引用任意工具"。
  要别的工具就先 eject，再写 ``core/scenarios/<name>/`` 的代码；
- 没有 cases.jsonl 就没有行为用例，评测页会显示空——不假装有；
- 仍然走 ``ensure_spec_editable``：代码目录一旦存在并被改动，构建直接失败。

这样控制台里"新建场景 -> 保存 -> 立刻能选、能跑"是真的，而不是存一份死 JSON。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from core.agent.contracts import Scenario
from core.llm.factory import chat_model
from core.scenarios.ownership import OWNER_CODE, ensure_spec_editable, load_state
from core.scenarios.spec import SpecError, build_from_spec, load_active_spec, resolve_cases_path
from core.scenarios.workspace_assistant.tools import (
    MemoryStore,
    NoteStore,
    build_workspace_tools,
)
from core.utils.path_tool import get_abs_path

SPEC_ROOT = Path(get_abs_path("data/specs"))
CODE_ROOT = Path(get_abs_path("core/scenarios"))
SEED_DIR = Path(get_abs_path("data/workspace_assistant/notes"))
USER_DIR = Path(get_abs_path("data/runtime/spec_scenarios/notes"))
MEMORY_DB = Path(get_abs_path("data/runtime/spec_scenarios/memory.sqlite"))


@lru_cache(maxsize=1)
def spec_tool_pool() -> tuple:
    """通用工具池：笔记检索 / 读写 + 长期记忆 + 翻译 / 总结。

    只读笔记来自 ``data/workspace_assistant/notes``，写入落在
    ``data/runtime/spec_scenarios/``，不碰其他场景的数据目录。
    """
    store = NoteStore(SEED_DIR, USER_DIR)
    memory = MemoryStore(MEMORY_DB)
    return tuple(build_workspace_tools(store, memory))


def spec_tool_names() -> list[str]:
    return [str(getattr(tool, "name", "")) for tool in spec_tool_pool()]


def spec_scenario_names(root: Path | str = SPEC_ROOT) -> list[str]:
    """列出"可以用 spec 构建"的场景：有 active.json 且没有 eject 过。"""
    directory_root = Path(root)
    if not directory_root.is_dir():
        return []
    names: list[str] = []
    for directory in sorted(directory_root.iterdir()):
        if not directory.is_dir():
            continue
        if not (directory / "active.json").is_file():
            continue
        state = load_state(directory.name, root)
        if state is not None and state.owner == OWNER_CODE:
            continue
        names.append(directory.name)
    return names


def is_spec_scenario(name: str, root: Path | str = SPEC_ROOT) -> bool:
    return name in spec_scenario_names(root)


def build_generic_spec_scenario(
    name: str,
    root: Path | str = SPEC_ROOT,
) -> Scenario:
    """用 spec + 通用工具池构建一个场景。"""
    ensure_spec_editable(name, root=root, code_root=CODE_ROOT)
    spec = load_active_spec(name, root=root)
    if spec is None:
        raise SpecError([f"没有找到 {name} 的 active spec：{Path(root) / name / 'active.json'}"])
    missing = [tool for tool in spec.tools if tool not in spec_tool_names()]
    if missing:
        raise SpecError([
            f"spec 引用了通用工具池里没有的工具：{', '.join(missing)}；"
            f"可用：{', '.join(spec_tool_names())}"
        ])
    return build_from_spec(
        spec,
        tools=list(spec_tool_pool()),
        model=chat_model,
        cases_path=resolve_cases_path(spec, root),
        checkpoint_backend="sqlite",
        checkpoint_path=f"data/runtime/spec_{name}_checkpoints.sqlite",
    )
