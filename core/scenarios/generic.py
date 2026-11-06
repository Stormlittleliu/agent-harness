# -*- coding: utf-8 -*-
"""通用 spec 场景：不写代码，只靠 ``data/specs/<name>/`` 也能构建出可跑的场景。

工具来自 ``core.scenarios.pools`` 的同名工具箱（没有专属池就走 office 兜底），
所以代码场景和它的 spec 仿造版用的是同一批工具。

边界（刻意的，别绕开）：

- 工具不能在 spec 里凭空声明，只能引用工具箱里已有的名字；
- 没有 cases.jsonl 就没有行为用例，评测页会显示空——不假装有；
- 仍然走 ``ensure_spec_editable``：代码目录一旦存在并被改动，构建直接失败。

这样控制台里"新建场景 -> 保存 -> 立刻能选、能跑"是真的，而不是存一份死 JSON。
"""
from __future__ import annotations

from pathlib import Path

from core.agent.contracts import Scenario
from core.prompts.blocks import load_book
from core.scenarios import pools
from core.scenarios.ownership import OWNER_CODE, ensure_spec_editable, load_state
from core.scenarios.spec import SpecError, build_from_spec, load_active_spec, resolve_cases_path
from core.scenarios.schemas import resolve as resolve_schema

from core.paths import PROJECT_ROOT, SPEC_ROOT

CODE_ROOT = PROJECT_ROOT / "core" / "scenarios"


def spec_tool_pool() -> tuple:
    """通用兜底池（控制台里新建、没有专属工具箱的场景用它）。"""
    return pools.toolbox("office").tools


def spec_tool_names() -> list[str]:
    return list(pools.tool_names("office"))


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
    """用 spec + 同名工具箱构建一个场景。"""
    from core.llm.factory import chat_model

    # spec 是权威：原代码目录（如果有）只剩参考价值，不再参与 hash 守卫。
    ensure_spec_editable(name, root=root, code_root=CODE_ROOT, track_code=False)
    spec = load_active_spec(name, root=root)
    if spec is None:
        raise SpecError([f"没有找到 {name} 的 active spec：{Path(root) / name / 'active.json'}"])
    box = pools.toolbox(name)
    available = {str(getattr(tool, "name", "")) for tool in box.tools}
    missing = [tool for tool in spec.tools if tool not in available]
    if missing:
        raise SpecError([
            f"spec 引用了工具箱 {box.name} 里没有的工具：{', '.join(missing)}；"
            f"可用：{', '.join(sorted(available)) or '（空）'}"
        ])
    book = load_book(Path(root) / name / "prompt.yml")
    return build_from_spec(
        spec,
        tools=list(box.tools),
        model=chat_model,
        cases_path=resolve_cases_path(spec, root),
        checkpoint_backend="sqlite",
        checkpoint_path=f"data/runtime/spec_{name}_checkpoints.sqlite",
        runtime=box.runtime,
        response_format=resolve_schema(spec.response_format),
        defaults=box.defaults,
        prompt_book=book,
    )
