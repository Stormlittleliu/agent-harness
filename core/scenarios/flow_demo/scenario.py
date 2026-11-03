# -*- coding: utf-8 -*-
"""flow_demo：由 spec 构建的场景，用来演示"场景即数据"。

它不是新的业务能力，只有一个工作流（检索 → 生成 → 引用校验）；
换流程不需要改这个文件，改的是 ``data/specs/flow_demo/vN.json``。
"""
from pathlib import Path

from core.llm.factory import chat_model
from core.scenarios.ownership import (
    OWNER_CODE,
    OwnershipError,
    ensure_spec_editable,
    load_state,
)
from core.scenarios.spec import SpecError, build_from_spec, load_active_spec
from core.scenarios.workspace_assistant.tools import (
    MemoryStore,
    NoteStore,
    build_workspace_tools,
)
from core.utils.path_tool import get_abs_path

SCENARIO_NAME = "flow_demo"
SPEC_ROOT = Path(get_abs_path("data/specs"))
SEED_DIR = Path(get_abs_path("data/workspace_assistant/notes"))
USER_DIR = Path(get_abs_path("data/runtime/flow_demo/notes"))
MEMORY_DB = Path(get_abs_path("data/runtime/flow_demo/memory.sqlite"))
CASES_PATH = Path(__file__).with_name("cases.jsonl")


SCENARIO_DIR = Path(__file__).resolve().parent


def build_scenario():
    state = load_state(SCENARIO_NAME, root=SPEC_ROOT)
    if state is not None and state.owner == OWNER_CODE:
        raise OwnershipError(
            f"{SCENARIO_NAME} 已转为 code-owned（{state.ejected_at or '未知时间'}）："
            "spec 不再参与构建。请在本文件的 build_scenario() 里直接实现场景。"
        )
    # spec-owned 下代码不许偷偷漂移：改了 core/scenarios/flow_demo/ 就必须先 eject。
    ensure_spec_editable(SCENARIO_NAME, root=SPEC_ROOT, code_root=SCENARIO_DIR.parent)

    spec = load_active_spec(SCENARIO_NAME, root=SPEC_ROOT)
    if spec is None:
        raise SpecError([
            f"没有找到 {SCENARIO_NAME} 的 active spec："
            f"{SPEC_ROOT / SCENARIO_NAME / 'active.json'}"
        ])
    store = NoteStore(SEED_DIR, USER_DIR)
    memory = MemoryStore(MEMORY_DB)
    tools = build_workspace_tools(store, memory)
    return build_from_spec(
        spec,
        tools=tools,
        model=chat_model,
        cases_path=CASES_PATH,
        checkpoint_backend="sqlite",
        checkpoint_path="data/runtime/flow_demo_checkpoints.sqlite",
    )
