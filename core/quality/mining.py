# -*- coding: utf-8 -*-
"""从评测轨迹里挖候选范式（M1，只读）。

输入是 ``outputs/runs/<run_id>/``（``run.json`` + ``lines.jsonl``），不重跑评测，
不改任何场景。做两层可解释的挖掘：

1. **连续序列**：把每次 trial 的 span 压成节点序列，找 support ≥ N 的连续子序列；
2. **转移 n-gram**：把相邻节点对 ``from → to`` 当 token，找高频转移。

排序分：``support × success_rate × lift / cost_penalty``。
只产出 candidate，**不自动采纳**；采纳是 M2/M3 的事。

用法::

    python -m core.quality.mining --scenario workspace_assistant --min-support 3 --top 10
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

from core.quality.paths import OUTPUTS_DIR
from core.quality.records import now_iso, read_run

MINING_VERSION = 1
DEFAULT_MIN_SUPPORT = 5
DEFAULT_MAX_LEN = 4
DEFAULT_TOP = 20
EVIDENCE_LIMIT = 10
COUNTEREXAMPLE_LIMIT = 5


@dataclass
class MinedLine:
    """一行 trial 的挖掘视图：保留 line_id 以便回到原始 run。"""

    line_id: str
    run_id: str
    scenario: str
    passed: bool
    sequence: list[str]
    intent: str = ""
    tokens: int = 0
    latency_ms: int = 0


@dataclass
class Pattern:
    """一条候选范式。字段对齐 ``docs/design/workflow-mining.md`` 的 pattern。"""

    pattern_id: str
    name: str
    kind: str  # sequence | transition
    scope: dict[str, Any]
    steps: list[str]
    transitions: list[list[str]]
    support: int
    total: int
    success_rate: float
    baseline: float
    lift: float
    cost: dict[str, float | int]
    evidence: list[str] = field(default_factory=list)
    counterexamples: list[str] = field(default_factory=list)
    score: float = 0.0
    source: str = "mined"
    status: str = "candidate"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------- 读数据


GENERIC_NODES = {"model", "tools", "agent", "llm", "chain"}


def _span_token(span: dict[str, Any]) -> str:
    """把一条 span 归一成一个可挖掘的 token。

    - spec 工作流的 trace 带真实节点名（``retrieve`` / ``answer``），直接用；
    - ReAct 的 trace 节点名是 ``model`` / ``tools`` 这类通用名，改用
      ``tool:search_notes`` / ``model``，否则整条序列全是 ``tools``；
    - 分支事件保留 ``branch:<name>``。
    """
    kind = str(span.get("kind") or "event")
    name = str(span.get("name") or "").strip()
    node = str((span.get("metadata") or {}).get("node") or "").strip()
    if node and node not in GENERIC_NODES:
        return node
    if kind in {"model", "llm"}:
        return "model"
    if kind == "tool":
        return f"tool:{name}" if name else (node or "tool")
    if kind == "branch":
        return f"branch:{name or node or 'branch'}"
    return name or node or kind


def node_sequence(spans: Iterable[dict[str, Any]]) -> list[str]:
    """把 span 压成节点/工具序列；相邻重复 token 只留一个。

    显式的 ``from_node`` / ``to_node`` 优先（未来的图转移事件）；
    其余按 ``_span_token`` 归一。
    """
    sequence: list[str] = []

    def push(name: str) -> None:
        name = str(name or "").strip()
        if name and (not sequence or sequence[-1] != name):
            sequence.append(name)

    for span in spans:
        metadata = span.get("metadata") or {}
        if (span.get("from_node") or span.get("to_node")) and not metadata.get("node"):
            push(str(span.get("from_node") or ""))
            push(str(span.get("to_node") or ""))
            continue
        push(_span_token(span))
    return sequence


def _line_cost(spans: Iterable[dict[str, Any]]) -> tuple[int, int]:
    tokens = 0
    latency = 0
    for span in spans:
        try:
            tokens += int(span.get("tokens") or 0)
        except (TypeError, ValueError):
            pass
        try:
            latency += int(span.get("latency_ms") or 0)
        except (TypeError, ValueError):
            pass
    return tokens, latency


def load_mined_lines(
    runs_root: Path | str | None = None,
    *,
    scenario: str | None = None,
) -> tuple[list[MinedLine], list[str]]:
    """读所有 run 目录，返回 ``(lines, run_ids)``。

    - 只认 ``run.json`` 存在且状态不是 ``failed/running`` 的 run；
    - 没有可用节点序列的 trial 跳过（没有 span 就挖不出过程）；
    - 一个 run 里场景不一致时以 line 自己的 ``scenario`` 为准。
    """
    root = Path(runs_root) if runs_root is not None else OUTPUTS_DIR / "runs"
    if not root.is_dir():
        return [], []

    lines: list[MinedLine] = []
    run_ids: list[str] = []
    for run_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        payload = read_run(run_dir)
        run = payload.get("run") or {}
        if not run:
            continue
        if str(run.get("status") or "completed") in {"failed", "running"}:
            continue
        run_scenario = str(run.get("scenario") or "")
        if scenario and run_scenario and run_scenario != scenario:
            continue
        run_ids.append(str(run.get("run_id") or run_dir.name))
        for line in payload.get("lines") or []:
            line_scenario = str(line.get("scenario") or run_scenario or "unknown")
            if scenario and line_scenario != scenario:
                continue
            sequence = node_sequence(line.get("spans") or [])
            if not sequence:
                continue
            tokens, latency = _line_cost(line.get("spans") or [])
            metadata = line.get("metadata") or {}
            lines.append(
                MinedLine(
                    line_id=str(line.get("line_id") or ""),
                    run_id=str(line.get("run_id") or run_dir.name),
                    scenario=line_scenario,
                    passed=str(line.get("status")) == "passed",
                    sequence=sequence,
                    intent=str(metadata.get("category") or ""),
                    tokens=tokens,
                    latency_ms=latency,
                )
            )
    return lines, run_ids


# ---------------------------------------------------------------- 序列挖掘


def _positions(sequence: Sequence[str], pattern: Sequence[str]) -> list[int]:
    size = len(pattern)
    if size == 0 or size > len(sequence):
        return []
    return [
        index
        for index in range(len(sequence) - size + 1)
        if list(sequence[index : index + size]) == list(pattern)
    ]


def _contains(sequence: Sequence[str], pattern: Sequence[str]) -> bool:
    return bool(_positions(sequence, pattern))


def frequent_sequences(
    transactions: list[list[str]],
    *,
    min_support: int,
    max_len: int,
    min_len: int = 3,
) -> dict[tuple[str, ...], set[int]]:
    """频繁连续子序列（自写 Apriori 式逐层扩展）。

    默认只返回长度 ≥ 3 的序列：两跳的 ``a → b`` 交给转移层，
    这样"序列"和"转移"不是同一件事的两种写法。
    返回 ``{pattern: 命中的 transaction 下标集合}``，不做带间隔的模式——
    轨迹里的顺序就是执行顺序，间隔模式解释性差。
    """
    if not transactions or min_support <= 0:
        return {}

    frequent: dict[tuple[str, ...], set[int]] = {}
    for index, sequence in enumerate(transactions):
        for token in set(sequence):
            frequent.setdefault((token,), set()).add(index)
    frequent = {key: hits for key, hits in frequent.items() if len(hits) >= min_support}

    found: dict[tuple[str, ...], set[int]] = {}
    length = 1
    while frequent and length < max_len:
        candidates: set[tuple[str, ...]] = set()
        for pattern, hits in frequent.items():
            for index in hits:
                sequence = transactions[index]
                for position in _positions(sequence, pattern):
                    end = position + len(pattern)
                    if end < len(sequence):
                        candidates.add(pattern + (sequence[end],))
        next_frequent: dict[tuple[str, ...], set[int]] = {}
        for candidate in candidates:
            hits = {
                index
                for index, sequence in enumerate(transactions)
                if _contains(sequence, candidate)
            }
            if len(hits) >= min_support:
                next_frequent[candidate] = hits
        for candidate, hits in next_frequent.items():
            if len(candidate) >= min_len:
                found[candidate] = hits
        frequent = next_frequent
        length += 1
    return found


def _cost_of(lines: list[MinedLine], hits: Iterable[int]) -> dict[str, float | int]:
    selected = [lines[index] for index in hits]
    if not selected:
        return {"avg_tokens": 0, "avg_latency_ms": 0}
    return {
        "avg_tokens": round(sum(line.tokens for line in selected) / len(selected), 1),
        "avg_latency_ms": round(sum(line.latency_ms for line in selected) / len(selected), 1),
    }


def _score(support: int, success_rate: float, lift: float, cost: dict[str, Any]) -> float:
    penalty = (
        1.0
        + float(cost.get("avg_tokens") or 0) / 4000.0
        + float(cost.get("avg_latency_ms") or 0) / 2000.0
    )
    return round(support * success_rate * max(lift, 0.0) / penalty, 4)


def _pattern_id(kind: str, scenario: str, intent: str, steps: Sequence[str]) -> str:
    raw = "|".join([kind, scenario, intent, ">".join(steps)])
    return "pat-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def _build_pattern(
    *,
    kind: str,
    steps: Sequence[str],
    scenario: str,
    intent: str,
    lines: list[MinedLine],
    success_hits: set[int],
    baseline: float,
) -> Pattern | None:
    all_hits = {
        index
        for index, line in enumerate(lines)
        if _contains(line.sequence, steps)
    }
    total = len(all_hits)
    if total == 0:
        return None
    success_rate = round(len(success_hits) / total, 4)
    lift = round(success_rate - baseline, 4)
    cost = _cost_of(lines, success_hits)
    transitions = [
        [steps[index], steps[index + 1]] for index in range(len(steps) - 1)
    ]
    scope: dict[str, Any] = {"scenario": scenario}
    if intent:
        scope["intent"] = intent
    return Pattern(
        pattern_id=_pattern_id(kind, scenario, intent, steps),
        name=" → ".join(steps),
        kind=kind,
        scope=scope,
        steps=list(steps),
        transitions=transitions,
        support=len(success_hits),
        total=total,
        success_rate=success_rate,
        baseline=baseline,
        lift=lift,
        cost=cost,
        evidence=[lines[index].line_id for index in sorted(success_hits)][:EVIDENCE_LIMIT],
        counterexamples=[
            lines[index].line_id for index in sorted(all_hits - success_hits)
        ][:COUNTEREXAMPLE_LIMIT],
        score=_score(len(success_hits), success_rate, lift, cost),
    )


def _mine_transitions(
    *,
    scenario: str,
    intent: str,
    lines: list[MinedLine],
    success_indexes: set[int],
    baseline: float,
    min_support: int,
) -> list[Pattern]:
    counts: dict[tuple[str, str], set[int]] = {}
    for index in success_indexes:
        sequence = lines[index].sequence
        for position in range(len(sequence) - 1):
            counts.setdefault((sequence[position], sequence[position + 1]), set()).add(index)
    patterns: list[Pattern] = []
    for pair, hits in counts.items():
        if len(hits) < min_support:
            continue
        pattern = _build_pattern(
            kind="transition",
            steps=pair,
            scenario=scenario,
            intent=intent,
            lines=lines,
            success_hits=hits,
            baseline=baseline,
        )
        if pattern is not None and pattern.lift > 0:
            patterns.append(pattern)
    return patterns


# ---------------------------------------------------------------- 主流程


def mine_patterns(
    lines: list[MinedLine],
    *,
    min_support: int = DEFAULT_MIN_SUPPORT,
    max_len: int = DEFAULT_MAX_LEN,
    top_k: int = DEFAULT_TOP,
) -> list[Pattern]:
    """按场景分桶挖掘，返回按 score 排序的 candidate 列表。

    只保留 ``lift > 0`` 的模式：成功率不高于 baseline 的“常见路径”不是范式，
    只是普通流程。support 只统计成功 trial；反例用于展示风险。
    """
    by_bucket: dict[tuple[str, str], list[MinedLine]] = {}
    for line in lines:
        by_bucket.setdefault((line.scenario, line.intent), []).append(line)

    patterns: list[Pattern] = []
    for (scenario, intent), bucket in sorted(by_bucket.items()):
        baseline = round(
            sum(1 for line in bucket if line.passed) / len(bucket), 4
        ) if bucket else 0.0
        success_indexes = {
            index for index, line in enumerate(bucket) if line.passed
        }
        if not success_indexes:
            continue
        success_transactions = [bucket[index].sequence for index in sorted(success_indexes)]
        index_by_order = [index for index in sorted(success_indexes)]

        found = frequent_sequences(
            success_transactions, min_support=min_support, max_len=max_len
        )
        seen_steps: set[tuple[str, ...]] = set()
        scenario_patterns: list[Pattern] = []
        for steps, hits in found.items():
            success_hits = {index_by_order[position] for position in hits}
            pattern = _build_pattern(
                kind="sequence",
                steps=steps,
                scenario=scenario,
                intent=intent,
                lines=bucket,
                success_hits=success_hits,
                baseline=baseline,
            )
            if pattern is None or pattern.lift <= 0:
                continue
            seen_steps.add(steps)
            scenario_patterns.append(pattern)

        for pattern in _mine_transitions(
            scenario=scenario,
            intent=intent,
            lines=bucket,
            success_indexes=success_indexes,
            baseline=baseline,
            min_support=min_support,
        ):
            if tuple(pattern.steps) in seen_steps:
                continue
            scenario_patterns.append(pattern)

        scenario_patterns.sort(key=lambda item: (-item.score, -item.support, item.name))
        patterns.extend(scenario_patterns[: max(1, int(top_k))])

    patterns.sort(key=lambda item: (-item.score, -item.support, item.name))
    return patterns


def _render_markdown(result: dict[str, Any]) -> str:
    patterns = result.get("patterns") or []
    lines = [
        "# 轨迹范式（候选，不自动采纳）",
        "",
        f"- mining_id：`{result.get('mining_id', '')}`",
        f"- 生成时间：{result.get('created_at', '')}",
        f"- 输入 run：{len(result.get('runs') or [])} 个",
        f"- 成功基线：" + "，".join(
            f"{name} {value:.2%}" for name, value in (result.get("baseline") or {}).items()
        ),
        f"- 参数：min_support={result.get('params', {}).get('min_support')}，"
        f"max_len={result.get('params', {}).get('max_len')}",
        "",
        "> 这些只是候选。采纳前必须走 held-out + A/B + 人工确认（M2/M3）。",
        "",
    ]
    if not patterns:
        baselines = list((result.get("baseline") or {}).values())
        if baselines and all(value >= 0.999 for value in baselines):
            lines.append(
                "没有可挖的范式：成功率基线已经是 100%，没有路径能超过基线。"
                "先跑出失败样本，再比较成功路径与失败路径的差异。"
            )
        else:
            lines.append("没有达到门槛的范式：成功率没有超过基线，或 support 不足。")
        return "\n".join(lines) + "\n"

    for index, pattern in enumerate(patterns, start=1):
        lines += [
            f"## {index}. {pattern['name']}",
            "",
            f"- 类型：{pattern['kind']} · 支持 **{pattern['support']}** 次成功"
            f" / 共 {pattern['total']} 次出现",
            f"- 成功率：{pattern['success_rate']:.2%}"
            f"（基线 {pattern['baseline']:.2%}，lift {pattern['lift']:+.2%}）",
            f"- 成本：约 {pattern['cost'].get('avg_tokens', 0)} tokens / "
            f"{pattern['cost'].get('avg_latency_ms', 0)} ms",
            f"- 证据：{', '.join(pattern['evidence']) or '（无）'}",
            f"- 反例：{', '.join(pattern['counterexamples']) or '（无）'}",
            "",
        ]
    return "\n".join(lines) + "\n"


def mine_and_write(
    *,
    runs_root: Path | str | None = None,
    out_root: Path | str | None = None,
    scenario: str | None = None,
    min_support: int = DEFAULT_MIN_SUPPORT,
    max_len: int = DEFAULT_MAX_LEN,
    top_k: int = DEFAULT_TOP,
    mining_id: str | None = None,
) -> dict[str, Any]:
    """读 run → 挖 → 写 ``patterns.json`` + ``patterns.md``，返回结果字典。"""
    lines, run_ids = load_mined_lines(runs_root, scenario=scenario)
    patterns = mine_patterns(
        lines, min_support=min_support, max_len=max_len, top_k=top_k
    )
    baseline: dict[str, float] = {}
    for line in lines:
        bucket = [item for item in lines if item.scenario == line.scenario]
        baseline[line.scenario] = round(
            sum(1 for item in bucket if item.passed) / len(bucket), 4
        )

    mining_id = mining_id or f"mine-{datetime.now():%Y%m%d-%H%M%S}"
    result = {
        "mining_version": MINING_VERSION,
        "mining_id": mining_id,
        "created_at": now_iso(),
        "runs": sorted(set(run_ids)),
        "line_count": len(lines),
        "scenarios": sorted({line.scenario for line in lines}),
        "baseline": baseline,
        "params": {
            "min_support": min_support,
            "max_len": max_len,
            "top_k": top_k,
        },
        "patterns": [pattern.to_dict() for pattern in patterns],
    }

    out_dir = Path(out_root) if out_root is not None else OUTPUTS_DIR / "patterns"
    target = out_dir / mining_id
    target.mkdir(parents=True, exist_ok=True)
    (target / "patterns.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    (target / "patterns.md").write_text(
        _render_markdown(result), encoding="utf-8", newline="\n"
    )
    result["out_dir"] = target.as_posix()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从评测 run 里挖候选范式（只读）")
    parser.add_argument("--runs-root", help="默认 outputs/runs")
    parser.add_argument("--out-root", help="默认 outputs/patterns")
    parser.add_argument("--scenario")
    parser.add_argument("--min-support", type=int, default=DEFAULT_MIN_SUPPORT)
    parser.add_argument("--max-len", type=int, default=DEFAULT_MAX_LEN)
    parser.add_argument("--top", type=int, default=DEFAULT_TOP)
    parser.add_argument("--id", help="mining_id；默认按时间生成")
    args = parser.parse_args(argv)

    result = mine_and_write(
        runs_root=args.runs_root,
        out_root=args.out_root,
        scenario=args.scenario,
        min_support=args.min_support,
        max_len=args.max_len,
        top_k=args.top,
        mining_id=args.id,
    )
    print(f"runs={len(result['runs'])} lines={result['line_count']} patterns={len(result['patterns'])}")
    for pattern in result["patterns"][:10]:
        print(
            f"  {pattern['score']:.3f}  {pattern['kind']:<10} "
            f"support={pattern['support']} success={pattern['success_rate']:.0%} "
            f"lift={pattern['lift']:+.0%}  {pattern['name']}"
        )
    print(f"out: {result['out_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
