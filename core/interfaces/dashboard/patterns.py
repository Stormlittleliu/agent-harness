# -*- coding: utf-8 -*-
"""质量页的「范式」视图：候选范式 → 候选 spec → shadow → 采纳/回退。

页面只做编排，判断都在 ``core.quality.adoption`` 与 ``core.scenarios.pattern_to_spec``：

- 没有 shadow 证据时「采纳」不可点；
- 门槛不过时列出原因，不写 active；
- 「回退」只把 active 指回 baseline，不删除新版本。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from core.interfaces.dashboard.common import load_agent, load_cases_cached
from core.interfaces.dashboard.layout import Kpi, empty_state, kpi_row, page_header, section
from core.quality.adoption import (
    AdoptionError,
    adopt_candidate,
    candidate_status,
    evaluate_gate,
    last_adoption,
    rollback_last,
)
from core.paths import SPEC_ROOT
from core.quality.paths import OUTPUTS_DIR
from core.quality.shadow import run_shadow
from core.scenarios.pattern_to_spec import (
    PatternCompileError,
    candidate_path,
    compile_pattern,
)
from core.scenarios.spec import SPEC_ROOT, build_from_spec, load_spec

PATTERN_ROOT = OUTPUTS_DIR / "patterns"
SHADOW_ROOT = OUTPUTS_DIR / "shadow"


def latest_patterns(root: Path | str | None = None) -> tuple[dict | None, Path | None]:
    """最近一次挖掘结果；没有就返回 ``(None, None)``。"""
    directory = Path(root) if root is not None else PATTERN_ROOT
    if not directory.is_dir():
        return None, None
    files = sorted(
        directory.glob("*/patterns.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            return data, path
    return None, None


def _latest_shadow(
    scenario: str,
    pattern_id: str,
    root: Path | str | None = None,
) -> dict | None:
    directory = Path(root) if root is not None else SHADOW_ROOT
    if not directory.is_dir():
        return None
    files = sorted(
        directory.glob("*/shadow.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (
            isinstance(data, dict)
            and data.get("scenario") == scenario
            and str(data.get("pattern_id") or "") == str(pattern_id)
        ):
            return data
    return None


def _reject(pattern: dict, patterns_path: Path) -> Path:
    target = patterns_path.parent / "rejected.json"
    payload = []
    if target.is_file():
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            payload = []
    if not isinstance(payload, list):
        payload = []
    payload.append({
        "pattern_id": pattern.get("pattern_id"),
        "name": pattern.get("name"),
        "rejected_at": datetime.now().isoformat(timespec="seconds"),
    })
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def build_candidate_agent(spec, base_scenario):
    """用 base 场景的工具/模型装配候选场景；只为 shadow 用，不替换 active。"""
    from core.agent.framework import FrameworkAgent
    from core.prompts.blocks import load_book

    book_path = SPEC_ROOT / spec.name / "prompt.yml"
    book = load_book(book_path)
    scenario = build_from_spec(
        spec,
        tools=list(base_scenario.tools),
        model=base_scenario.model,
        cases_path=base_scenario.cases_path,
        checkpoint_backend="memory",
        checkpoint_path=f"data/runtime/shadow_{spec.name}.sqlite",
        runtime=base_scenario.runtime,
        response_format=base_scenario.response_format,
        prompt_book=book,
    )
    return FrameworkAgent(scenario)


def _run_shadow_for(scenario: str, pattern_id: str) -> dict:
    from core.quality.agent_eval import load_cases

    status = candidate_status(scenario, pattern_id)
    if not status["exists"]:
        raise RuntimeError("候选 spec 不存在，先点「编译成候选」")
    base_agent = load_agent(scenario)
    candidate_spec = load_spec(status["path"])
    candidate_agent = build_candidate_agent(candidate_spec, base_agent.scenario)
    cases, error = load_cases_cached(base_agent.scenario.cases_path)
    if error:
        raise RuntimeError(f"读取用例失败：{error}")
    if not cases:
        cases = load_cases(base_agent.scenario.cases_path) if base_agent.scenario.cases_path else []
    if not cases:
        raise RuntimeError("场景没有行为用例，无法做 shadow")
    return run_shadow(
        base_agent,
        candidate_agent,
        list(cases)[:8],
        scenario=scenario,
        pattern_id=pattern_id,
        held_out_ratio=0.3,
        seed=f"{scenario}:{pattern_id}",
        trials=1,
    )


def render_patterns(scenario: str) -> None:
    page_header(
        "范式",
        "从成功轨迹挖出的候选。先编译成候选 spec，再用 shadow 拿证据；"
        "采纳要过门槛，且随时可以回退。",
    )
    payload, patterns_path = latest_patterns()
    if payload is None:
        empty_state(
            "还没有范式。先跑一次评测，再执行挖掘。",
            "python -m core.quality.mining --scenario " + scenario,
        )
        return

    patterns = payload.get("patterns") or []
    mining_id = payload.get("mining_id", "")
    st.caption(
        f"挖掘 `{mining_id}` · 成功基线 "
        + "，".join(
            f"{name} {value:.0%}" for name, value in (payload.get("baseline") or {}).items()
        )
        + f" · {payload.get('line_count', 0)} 条 trial"
    )
    if not patterns:
        st.info("最近一次挖掘没有达到门槛的范式；先跑出失败样本，再比较成功与失败路径。")
        return

    labels = [
        f"{pattern['name']} · support {pattern['support']} · lift {pattern['lift']:+.0%}"
        for pattern in patterns
    ]
    index = st.selectbox(
        "选择范式",
        range(len(patterns)),
        format_func=lambda value: labels[value],
        key=f"quality:pattern:{scenario}",
    )
    pattern = patterns[index]
    pattern_id = str(pattern.get("pattern_id") or "")

    chain = " → ".join(f"`{step}`" for step in pattern.get("steps") or [])
    st.markdown(chain or "（没有步骤）")
    kpi_row([
        Kpi("支持", str(pattern.get("support", 0)), help="成功 trial 里的出现次数"),
        Kpi("成功率", f"{pattern.get('success_rate', 0):.0%}", help=f"基线 {pattern.get('baseline', 0):.0%}"),
        Kpi("lift", f"{pattern.get('lift', 0):+.0%}", help="成功率 - 基线"),
        Kpi("成本", f"{pattern.get('cost', {}).get('avg_tokens', 0)} tok", help="匹配 trial 的平均 token"),
    ])

    left, right = st.columns([1.2, 1], gap="medium")
    with left:
        st.caption("证据（成功 run）")
        st.code("\n".join(pattern.get("evidence") or []) or "—", language=None)
    with right:
        st.caption("反例（失败 run）")
        st.code("\n".join(pattern.get("counterexamples") or []) or "—", language=None)

    status = candidate_status(scenario, pattern_id)
    if status["exists"]:
        st.caption(f"候选：`{status['path']}`")
    else:
        st.caption("还没有候选 spec。")

    actions = st.columns(4, gap="small")
    if actions[0].button("编译成候选", key=f"quality:compile:{scenario}:{pattern_id}"):
        try:
            source = load_spec(status["path"]) if status["exists"] else None
            from core.scenarios.spec import load_active_spec

            source = source or load_active_spec(scenario)
            candidate = compile_pattern(
                pattern,
                scenario=scenario,
                source_spec=source,
                tool_names=set(source.tools) if source is not None else set(),
                root=SPEC_ROOT,
            )
        except PatternCompileError as exc:
            st.error("编译失败：")
            for error in exc.errors:
                st.markdown(f"- {error}")
        else:
            st.success(f"已写候选：{candidate.path}")
            st.rerun()

    shadow = st.session_state.get(f"quality:shadow:{scenario}:{pattern_id}") or _latest_shadow(
        scenario, pattern_id
    )
    if actions[1].button("试运行 shadow", key=f"quality:shadow:{scenario}:{pattern_id}"):
        try:
            with st.spinner("正在跑 baseline / candidate（会真实调用模型）…"):
                shadow = _run_shadow_for(scenario, pattern_id)
        except Exception as exc:  # noqa: BLE001 - 页面给出原因
            st.error(f"shadow 失败：{type(exc).__name__}: {exc}")
        else:
            st.session_state[f"quality:shadow:{scenario}:{pattern_id}"] = shadow
            st.success(f"shadow 已记录：{shadow.get('out_dir')}")

    gate = evaluate_gate(shadow) if shadow else None
    if gate is not None:
        if gate.passed:
            st.success("A/B 门槛通过：可以人工采纳。")
        else:
            st.warning("A/B 门槛未通过：")
            for reason in gate.reasons:
                st.markdown(f"- {reason}")
        with st.expander("shadow 明细", expanded=False):
            st.json({
                "shadow_id": shadow.get("shadow_id"),
                "baseline": shadow.get("baseline"),
                "candidate": shadow.get("candidate"),
                "comparison": shadow.get("comparison"),
                "decision": shadow.get("decision"),
            })

    if actions[2].button(
        "采纳",
        key=f"quality:adopt:{scenario}:{pattern_id}",
        disabled=gate is None or not gate.passed,
    ):
        try:
            record = adopt_candidate(
                scenario,
                status["path"],
                gate,
                shadow_id=str(shadow.get("shadow_id") or ""),
            )
        except AdoptionError as exc:
            st.error("；".join(exc.errors))
        else:
            load_agent.clear()
            st.success(f"已采纳 {record['adopted_version']}；baseline {record['baseline_version']} 保留")
            st.rerun()

    adoption = last_adoption(scenario)
    if actions[3].button(
        "回退",
        key=f"quality:rollback:{scenario}",
        disabled=not bool(adoption),
    ):
        try:
            record = rollback_last(scenario)
        except AdoptionError as exc:
            st.error("；".join(exc.errors))
        else:
            load_agent.clear()
            st.success(f"已回退到 {record['restored_version']}")
            st.rerun()

    if st.button("拒绝这条范式", key=f"quality:reject:{scenario}:{pattern_id}"):
        target = _reject(pattern, patterns_path)
        st.success(f"已记录拒绝：{target}")
