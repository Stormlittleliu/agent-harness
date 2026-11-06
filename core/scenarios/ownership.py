# -*- coding: utf-8 -*-
"""场景归属：spec-owned（可低代码编辑）还是 code-owned（只能看）。

设计原则：**不靠 agent 自觉，靠构建期强校验。**

- spec-owned：``data/specs/<name>`` 是权威，代码改了却没收尾 -> 构建直接失败；
- code-owned：代码是权威，spec 变成历史文件，可视化从已编译图内省，天然同步；
- 归属只由 ``state.json`` 决定，状态迁移只有一个入口：``python -m core.scenarios.eject``。

为什么"同步可视化"不需要 agent 做事：code 模式下可视化不读 spec，读的是
``compiled_graph.get_graph()``。结构只有一份来源，就没有可漂移的副本。
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import PROJECT_ROOT, SPEC_ROOT as _SPEC_ROOT

SPEC_ROOT = _SPEC_ROOT
CODE_ROOT = PROJECT_ROOT / "core" / "scenarios"
STATE_FILE = "state.json"

OWNER_SPEC = "spec"
OWNER_CODE = "code"


class OwnershipError(RuntimeError):
    """归属冲突：必须先显式 eject，才能继续改场景代码。"""


@dataclass(frozen=True)
class ScenarioState:
    name: str
    owner: str = OWNER_SPEC
    code_hash: str | None = None
    spec_file: str | None = None
    ejected_at: str | None = None
    reason: str | None = None

    @property
    def editable(self) -> bool:
        return self.owner == OWNER_SPEC

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScenarioState":
        known = {field: data[field] for field in cls.__dataclass_fields__ if field in data}
        return cls(**known)


def state_path(name: str, root: Path | str = SPEC_ROOT) -> Path:
    return Path(root) / name / STATE_FILE


def scenario_code_hash(name: str, code_root: Path | str = CODE_ROOT) -> str:
    """把 ``core/scenarios/<name>/`` 下所有 .py 按路径排序后一起摘要。"""
    directory = Path(code_root) / name
    digest = hashlib.sha256()
    files = sorted(
        path
        for path in directory.rglob("*.py")
        if "__pycache__" not in path.parts
    )
    for path in files:
        digest.update(path.relative_to(directory).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def load_state(name: str, root: Path | str = SPEC_ROOT) -> ScenarioState | None:
    path = state_path(name, root)
    if not path.is_file():
        return None
    try:
        return ScenarioState.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def save_state(state: ScenarioState, root: Path | str = SPEC_ROOT) -> Path:
    path = state_path(state.name, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(path)
    return path


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def eject(
    name: str,
    reason: str = "",
    root: Path | str = SPEC_ROOT,
    code_root: Path | str = CODE_ROOT,
) -> ScenarioState:
    """把场景永久转为 code-owned。这是唯一的单向门。"""
    state = ScenarioState(
        name=name,
        owner=OWNER_CODE,
        code_hash=scenario_code_hash(name, code_root),
        spec_file=(load_state(name, root).spec_file if load_state(name, root) else None),
        ejected_at=_now(),
        reason=reason or None,
    )
    save_state(state, root)
    return state


def ensure_spec_editable(
    name: str,
    root: Path | str = SPEC_ROOT,
    code_root: Path | str = CODE_ROOT,
    track_code: bool = True,
) -> ScenarioState:
    """spec 场景构建前的守卫：已 eject 或代码漂移都直接失败。

    首次调用会写入基线 state（owner=spec + 当前代码 hash）。

    ``track_code=False`` 用于"spec 已经接管、原代码目录只剩参考价值"的场景：
    仍然禁止使用已 eject 的 spec，但不再因为参考代码被改动而报错
    （那时 spec 才是权威，代码分叉是预期内的）。
    """
    state = load_state(name, root)
    if state is None:
        state = ScenarioState(
            name=name,
            owner=OWNER_SPEC,
            code_hash=scenario_code_hash(name, code_root) if track_code else None,
        )
        save_state(state, root)
        return state

    if state.owner != OWNER_SPEC:
        raise OwnershipError(
            f"场景 {name} 已转为 code-owned（{state.ejected_at or '未知时间'}），"
            "spec 不再参与构建，也不能再用低代码编辑。"
        )

    if not track_code:
        if state.code_hash is not None:
            state = replace(state, code_hash=None)
            save_state(state, root)
        return state

    current = scenario_code_hash(name, code_root)
    if state.code_hash and current != state.code_hash:
        raise OwnershipError(
            f"场景 {name} 的代码已被修改，spec 与代码分叉。\n"
            f"请先运行：python -m core.scenarios.eject {name} --reason \"说明\"\n"
            "运行后会把它转为 code-owned：spec 失效、可视化变为只读、构建改用代码。"
        )
    return state


def status(
    name: str,
    root: Path | str = SPEC_ROOT,
    code_root: Path | str = CODE_ROOT,
) -> dict[str, Any]:
    """给编码 agent / CLI 的自查入口。"""
    state = load_state(name, root)
    current = scenario_code_hash(name, code_root)
    if state is None:
        return {
            "scenario": name,
            "owner": None,
            "editable": None,
            "code_hash": current,
            "hash_match": None,
            "next_action": f"python -m core.scenarios.eject {name} --status",
        }
    match = state.code_hash is None or state.code_hash == current
    if state.owner == OWNER_CODE:
        action = "只读：spec 已失效，改 core/scenarios/<name>/ 下的代码"
    elif not match:
        action = f"代码已漂移：先运行 python -m core.scenarios.eject {name}"
    else:
        action = "可低代码编辑：改 data/specs/<name>/v*.json"
    return {
        "scenario": name,
        "owner": state.owner,
        "editable": state.editable and match,
        "code_hash": current,
        "recorded_hash": state.code_hash,
        "hash_match": match,
        "ejected_at": state.ejected_at,
        "next_action": action,
    }
