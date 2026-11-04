# -*- coding: utf-8 -*-
"""范式候选的采纳门槛与回退（M3）。

三条硬约束：

- **不自动采纳**：只有显式调用 ``adopt_candidate`` 且 gate 通过才写 active；
- **保留 baseline**：采纳只是新增一个版本，旧版本文件原样保留；
- **可回退**：回退只把 ``active.json`` 指回 baseline，不删除新版本，也不改历史。

门槛（缺一不可）：

- pass^k 不低于 baseline；
- outcome 通过率不低于 baseline（没有 outcome 数据时不做判断）；
- 平均 token / 延迟不超过 baseline 的预算倍数；
- 没有安全回归（``safety_regressions`` 为空）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from core.quality.paths import OUTPUTS_DIR
from core.scenarios.spec import (
    SPEC_ROOT,
    active_spec_path,
    load_spec,
    save_spec,
    validate_spec,
)

DEFAULT_MAX_COST_RATIO = 1.25
DEFAULT_MAX_LATENCY_RATIO = 1.5


class AdoptionError(ValueError):
    """采纳/回退被拒绝；``errors`` 是逐条原因。"""

    def __init__(self, errors: list[str]):
        self.errors = list(errors)
        super().__init__("；".join(self.errors))


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _num(section: dict[str, Any], key: str) -> float | None:
    value = (section or {}).get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class GateResult:
    passed: bool
    pass_k_ok: bool
    outcome_ok: bool
    cost_ok: bool
    latency_ok: bool
    safety_ok: bool
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "pass_k_ok": self.pass_k_ok,
            "outcome_ok": self.outcome_ok,
            "cost_ok": self.cost_ok,
            "latency_ok": self.latency_ok,
            "safety_ok": self.safety_ok,
            "reasons": list(self.reasons),
            "metrics": dict(self.metrics),
        }


def evaluate_gate(
    shadow: dict[str, Any],
    *,
    max_cost_ratio: float = DEFAULT_MAX_COST_RATIO,
    max_latency_ratio: float = DEFAULT_MAX_LATENCY_RATIO,
) -> GateResult:
    """按 shadow 结果判断候选能不能进入人工采纳。"""
    baseline = shadow.get("baseline") or {}
    candidate = shadow.get("candidate") or {}
    comparison = shadow.get("comparison") or {}

    baseline_pass = _num(baseline, "pass_k")
    candidate_pass = _num(candidate, "pass_k")
    if baseline_pass is None:
        baseline_pass = _num(baseline, "pass_rate") or 0.0
    if candidate_pass is None:
        candidate_pass = _num(candidate, "pass_rate") or 0.0
    pass_k_ok = candidate_pass >= baseline_pass

    baseline_outcome = _num(baseline, "outcome_rate")
    candidate_outcome = _num(candidate, "outcome_rate")
    outcome_ok = (
        True
        if baseline_outcome is None or candidate_outcome is None
        else candidate_outcome >= baseline_outcome
    )

    baseline_tokens = _num(baseline, "avg_tokens") or 0.0
    candidate_tokens = _num(candidate, "avg_tokens") or 0.0
    cost_ok = (
        True
        if baseline_tokens <= 0
        else candidate_tokens <= baseline_tokens * max(1.0, float(max_cost_ratio))
    )

    baseline_latency = _num(baseline, "avg_latency_ms") or 0.0
    candidate_latency = _num(candidate, "avg_latency_ms") or 0.0
    latency_ok = (
        True
        if baseline_latency <= 0
        else candidate_latency <= baseline_latency * max(1.0, float(max_latency_ratio))
    )

    safety_regressions = list(comparison.get("safety_regressions") or [])
    safety_ok = not safety_regressions

    reasons: list[str] = []
    if not pass_k_ok:
        reasons.append(f"pass^k 下降：{baseline_pass:.4f} → {candidate_pass:.4f}")
    if not outcome_ok:
        reasons.append(f"outcome 通过率下降：{baseline_outcome} → {candidate_outcome}")
    if not cost_ok:
        reasons.append(
            f"token 成本超预算：{baseline_tokens:.1f} → {candidate_tokens:.1f}"
            f"（上限 {max_cost_ratio:.2f}×）"
        )
    if not latency_ok:
        reasons.append(
            f"延迟超预算：{baseline_latency:.0f}ms → {candidate_latency:.0f}ms"
            f"（上限 {max_latency_ratio:.2f}×）"
        )
    if not safety_ok:
        reasons.append("安全回归：" + "、".join(safety_regressions))

    return GateResult(
        passed=all([pass_k_ok, outcome_ok, cost_ok, latency_ok, safety_ok]),
        pass_k_ok=pass_k_ok,
        outcome_ok=outcome_ok,
        cost_ok=cost_ok,
        latency_ok=latency_ok,
        safety_ok=safety_ok,
        reasons=reasons,
        metrics={
            "baseline_pass_k": baseline_pass,
            "candidate_pass_k": candidate_pass,
            "baseline_outcome": baseline_outcome,
            "candidate_outcome": candidate_outcome,
            "baseline_avg_tokens": baseline_tokens,
            "candidate_avg_tokens": candidate_tokens,
            "baseline_avg_latency_ms": baseline_latency,
            "candidate_avg_latency_ms": candidate_latency,
        },
    )


def _records_dir(scenario: str, out_root: Path | str | None) -> Path:
    root = Path(out_root) if out_root is not None else OUTPUTS_DIR / "adoptions"
    return root / scenario


def _write_record(record: dict[str, Any], out_root: Path | str | None) -> Path:
    directory = _records_dir(record["scenario"], out_root)
    directory.mkdir(parents=True, exist_ok=True)
    name = f"{record['adoption_id']}.json"
    target = directory / name
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(target)
    return target


def _active_version(scenario: str, root: Path | str) -> tuple[str | None, str | None]:
    path = active_spec_path(scenario, root)
    if path is None:
        return None, None
    return path.stem, path.name


def adopt_candidate(
    scenario: str,
    candidate_path: Path | str,
    gate: GateResult | dict[str, Any],
    *,
    shadow_id: str = "",
    root: Path | str = SPEC_ROOT,
    out_root: Path | str | None = None,
) -> dict[str, Any]:
    """把候选写成新版本并设为 active；baseline 版本保留，可回退。"""
    gate_data = gate.to_dict() if isinstance(gate, GateResult) else dict(gate)
    if not gate_data.get("passed"):
        raise AdoptionError(list(gate_data.get("reasons") or ["A/B 门槛未通过"]))

    baseline_version, baseline_file = _active_version(scenario, root)
    if baseline_version is None:
        raise AdoptionError([f"{scenario} 没有 active spec，无法保留 baseline，不允许采纳"])

    candidate = Path(candidate_path)
    if not candidate.is_file():
        raise AdoptionError([f"候选文件不存在：{candidate}"])
    spec = load_spec(candidate)
    if spec.name != scenario:
        raise AdoptionError([f"候选场景名 {spec.name} 与目标 {scenario} 不一致"])

    active = load_spec(active_spec_path(scenario, root))
    errors = validate_spec(spec, tool_names=set(active.tools))
    if errors:
        raise AdoptionError([f"候选校验失败：{error}" for error in errors])

    adopted_at = _now()
    spec.provenance = {
        **(spec.provenance or {}),
        "status": "adopted",
        "adopted_at": adopted_at,
        "shadow_id": shadow_id,
        "baseline_version": baseline_version,
    }
    new_path = save_spec(spec, root=root, make_active=True)
    adoption_id = f"adopt-{datetime.now():%Y%m%d-%H%M%S}"
    record = {
        "adoption_id": adoption_id,
        "scenario": scenario,
        "action": "adopted",
        "created_at": adopted_at,
        "pattern_id": (spec.provenance or {}).get("pattern_id") or "",
        "candidate": candidate.as_posix(),
        "shadow_id": shadow_id,
        "gate": gate_data,
        "baseline_version": baseline_version,
        "baseline_file": baseline_file,
        "adopted_version": new_path.stem,
        "adopted_file": new_path.name,
    }
    record["record_path"] = _write_record(record, out_root).as_posix()
    return record


def _adoption_records(
    scenario: str,
    out_root: Path | str | None,
    *,
    action: str = "adopted",
) -> list[dict[str, Any]]:
    directory = _records_dir(scenario, out_root)
    if not directory.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("action") == action:
            records.append(data)
    return records


def last_adoption(
    scenario: str,
    *,
    out_root: Path | str | None = None,
) -> dict[str, Any] | None:
    records = _adoption_records(scenario, out_root)
    if not records:
        return None
    return max(records, key=lambda item: str(item.get("created_at") or ""))


def rollback_last(
    scenario: str,
    *,
    root: Path | str = SPEC_ROOT,
    out_root: Path | str | None = None,
) -> dict[str, Any]:
    """把 active 指回最近一次采纳前的 baseline；不删除新版本。"""
    adoption = last_adoption(scenario, out_root=out_root)
    if adoption is None:
        raise AdoptionError([f"{scenario} 没有可回退的采纳记录"])
    restored = str(adoption.get("baseline_version") or "")
    directory = Path(root) / scenario
    target = directory / f"{restored}.json"
    if not restored or not target.is_file():
        raise AdoptionError([f"baseline 版本不存在：{restored or '（空）'}"])

    try:
        version = int(restored.lstrip("v"))
    except ValueError as exc:
        raise AdoptionError([f"baseline 版本号不合法：{restored}"]) from exc
    pointer = {"version": version, "file": target.name}
    tmp = directory / "active.json.tmp"
    tmp.write_text(
        json.dumps(pointer, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    tmp.replace(directory / "active.json")

    record = {
        "adoption_id": f"rollback-{datetime.now():%Y%m%d-%H%M%S}",
        "scenario": scenario,
        "action": "rolled_back",
        "created_at": _now(),
        "restored_version": restored,
        "restored_file": target.name,
        "from_adoption": adoption.get("adoption_id"),
        "adopted_version": adoption.get("adopted_version"),
    }
    record["record_path"] = _write_record(record, out_root).as_posix()
    return record


def candidate_status(
    scenario: str,
    pattern_id: str,
    *,
    root: Path | str = SPEC_ROOT,
    out_root: Path | str | None = None,
) -> dict[str, Any]:
    """给页面用：候选是否存在、是否已经采纳。"""
    from core.scenarios.pattern_to_spec import candidate_path

    path = candidate_path(scenario, pattern_id, root)
    adoption = last_adoption(scenario, out_root=out_root)
    return {
        "path": path.as_posix(),
        "exists": path.is_file(),
        "adopted": bool(
            adoption
            and adoption.get("scenario") == scenario
            and str(adoption.get("pattern_id") or "") == str(pattern_id)
        ),
        "last_adoption": adoption,
    }
