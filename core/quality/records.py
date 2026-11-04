# -*- coding: utf-8 -*-
"""评测运行记录：run / line / span / score。

这是质量层与轨迹挖掘的共同地基：一次评测是一个 ``RunRecord``，每条用例的
每次 trial 是一条 ``LineRecord``，节点/工具调用是 ``Span``，评分是 ``Score``。

落盘目录::

    outputs/runs/<run_id>/
      run.json        # 运行头：场景、用例数、trials、指标、时间
      lines.jsonl     # 一行一条 trial；稳定 line_id = <run_id>:<index>
      metrics.json    # 从 lines 聚合出来的指标；页面只读这里

设计约束：

- 只写 JSON/JSONL，不引入数据库；Streamlit 直接读目录。
- ``line_id`` 稳定且可读，方便 trace / pattern 反查。
- 指标在 run 结束聚合落盘，不在页面现算。
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from core.quality.paths import OUTPUTS_DIR

RECORD_VERSION = 1


def now_iso() -> str:
    """本地时区 ISO 时间；评测报告用本地时间更直观。"""
    return datetime.now().isoformat(timespec="seconds")


def new_run_id(prefix: str = "run") -> str:
    return f"{prefix}-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"


@dataclass
class Score:
    """单条判定。行为 / outcome / judge 都归一到这个形状。"""

    name: str
    value: float
    passed: bool
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Span:
    """轨迹里的一个节点/工具/分支事件。"""

    span_id: str
    name: str
    kind: str = "node"  # node | tool | branch | retry | interrupt | error
    status: str = "ok"
    parent_id: str | None = None
    latency_ms: int | None = None
    tokens: int | None = None
    args_digest: str | None = None
    args_summary: str | None = None
    from_node: str | None = None
    to_node: str | None = None
    condition: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LineRecord:
    """一次 case × trial 的运行记录。"""

    line_id: str
    run_id: str
    case_id: str
    trial: int
    scenario: str
    status: str
    started_at: str = field(default_factory=now_iso)
    ended_at: str = field(default_factory=now_iso)
    trace_id: str | None = None
    answer: str = ""
    tool_names: list[str] = field(default_factory=list)
    scores: list[Score] = field(default_factory=list)
    spans: list[Span] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["scores"] = [score.to_dict() for score in self.scores]
        data["spans"] = [span.to_dict() for span in self.spans]
        return data


def _scores_from(value: Iterable[Score | dict[str, Any]] | None) -> list[Score]:
    scores: list[Score] = []
    for item in value or []:
        if isinstance(item, Score):
            scores.append(item)
            continue
        if isinstance(item, dict):
            scores.append(
                Score(
                    name=str(item.get("name") or "score"),
                    value=float(item.get("value") or 0.0),
                    passed=bool(item.get("passed")),
                    reason=str(item.get("reason") or ""),
                    metadata=dict(item.get("metadata") or {}),
                )
            )
    return scores


def _score_metrics(lines: list[LineRecord]) -> dict[str, dict[str, float | int]]:
    """按 score.name 聚合 mean / pass_rate / count。"""
    grouped: dict[str, list[Score]] = {}
    for line in lines:
        for score in line.scores:
            grouped.setdefault(score.name, []).append(score)
    metrics: dict[str, dict[str, float | int]] = {}
    for name, scores in grouped.items():
        values = [float(score.value) for score in scores]
        passed = [1.0 if score.passed else 0.0 for score in scores]
        metrics[name] = {
            "count": len(scores),
            "mean": round(sum(values) / len(values), 4) if values else 0.0,
            "pass_rate": round(sum(passed) / len(passed), 4) if passed else 0.0,
        }
    return metrics


def _pass_k(lines: list[LineRecord], k: int) -> float:
    """按 case 聚合：同一 case 的 k 次 trial 全部通过才算 pass^k。"""
    k = max(1, int(k))
    by_case: dict[str, list[bool]] = {}
    for line in lines:
        by_case.setdefault(line.case_id, []).append(line.status == "passed")
    if not by_case:
        return 0.0
    passed = 0
    for values in by_case.values():
        window = values[:k]
        if len(window) < k:
            continue
        if all(window):
            passed += 1
    total = sum(1 for values in by_case.values() if len(values) >= k)
    return round(passed / total, 4) if total else 0.0


class RunStore:
    """一次评测的目录写入器。"""

    def __init__(
        self,
        run_id: str | None = None,
        *,
        root: Path | None = None,
        scenario: str = "",
        kind: str = "agent",
        trials: int = 1,
        tags: Iterable[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.run_id = run_id or new_run_id()
        self.root = Path(root) if root is not None else OUTPUTS_DIR / "runs"
        self.run_dir = self.root / self.run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.scenario = scenario
        self.kind = kind
        self.trials = max(1, int(trials or 1))
        self.tags = list(tags or [])
        self.metadata = dict(metadata or {})
        self.created_at = now_iso()
        self._lines: list[LineRecord] = []
        self._line_path = self.run_dir / "lines.jsonl"
        self._line_path.touch(exist_ok=True)

    @property
    def lines(self) -> list[LineRecord]:
        return list(self._lines)

    def record_line(
        self,
        *,
        case_id: str,
        trial: int,
        scenario: str,
        passed: bool,
        scores: Iterable[Score | dict[str, Any]] | None = None,
        trace_id: str | None = None,
        answer: str = "",
        tool_names: Iterable[str] | None = None,
        spans: Iterable[Span | dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LineRecord:
        index = len(self._lines) + 1
        line = LineRecord(
            line_id=f"{self.run_id}:{index}",
            run_id=self.run_id,
            case_id=str(case_id),
            trial=max(1, int(trial)),
            scenario=scenario,
            status="passed" if passed else "failed",
            trace_id=trace_id,
            answer=str(answer or ""),
            tool_names=list(tool_names or []),
            scores=_scores_from(scores),
            spans=[
                span if isinstance(span, Span) else Span(**span)
                for span in (spans or [])
            ],
            metadata=dict(metadata or {}),
        )
        self._lines.append(line)
        with self._line_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line.to_dict(), ensure_ascii=False) + "\n")
        return line

    def finalize(
        self,
        *,
        summary: dict[str, Any] | None = None,
        status: str = "completed",
    ) -> dict[str, Any]:
        """聚合指标并写 run.json / metrics.json。可重复调用。"""
        metrics = _score_metrics(self._lines)
        metrics["pass^k"] = {
            "k": self.trials,
            "value": _pass_k(self._lines, self.trials),
            "count": len(self._lines),
        }
        metrics["overall"] = {
            "count": len(self._lines),
            "pass_rate": round(
                sum(1 for line in self._lines if line.status == "passed")
                / len(self._lines),
                4,
            )
            if self._lines
            else 0.0,
        }
        run = {
            "record_version": RECORD_VERSION,
            "run_id": self.run_id,
            "kind": self.kind,
            "scenario": self.scenario,
            "created_at": self.created_at,
            "finished_at": now_iso(),
            "status": status,
            "trials": self.trials,
            "line_count": len(self._lines),
            "case_count": len({line.case_id for line in self._lines}),
            "tags": self.tags,
            "metadata": self.metadata,
            "summary": dict(summary or {}),
            "metrics": metrics,
        }
        (self.run_dir / "metrics.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (self.run_dir / "run.json").write_text(
            json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return run


def read_run(run_dir: Path) -> dict[str, Any]:
    """读一个 run 目录；缺失文件给空值，方便页面容错。"""
    run_dir = Path(run_dir)
    run_path = run_dir / "run.json"
    metrics_path = run_dir / "metrics.json"
    line_path = run_dir / "lines.jsonl"
    run = json.loads(run_path.read_text(encoding="utf-8")) if run_path.exists() else {}
    metrics = (
        json.loads(metrics_path.read_text(encoding="utf-8"))
        if metrics_path.exists()
        else {}
    )
    lines: list[dict[str, Any]] = []
    if line_path.exists():
        for line in line_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                lines.append(json.loads(line))
    return {"run": run, "metrics": metrics, "lines": lines}
