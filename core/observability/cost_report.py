# -*- coding: utf-8 -*-
"""成本 / 时延报告：把本地 trace 聚合成一页可复现的指标。

输入：``outputs/traces/trace_*.jsonl``（TraceCallbackHandler 逐行写入）
输出：JSON + Markdown；不调用模型，不依赖 LangSmith。

用法：
    python -m core.observability.cost_report
    python -m core.observability.cost_report --trace-dir outputs/traces --out outputs/cost_report.md
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRACE_DIR = ROOT / "outputs" / "traces"
DEFAULT_OUT = ROOT / "outputs" / "cost_report.md"
DEFAULT_JSON = ROOT / "outputs" / "cost_report.json"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def load_pricing(path: Path | None = None) -> dict:
    """读取 config/observability.yml 的单价；缺失或格式错误时返回空表。"""
    path = path or (ROOT / "config" / "observability.yml")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    pricing = data.get("pricing") if isinstance(data, dict) else {}
    return pricing if isinstance(pricing, dict) else {}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int, pricing: dict) -> float:
    """按每百万 token 单价估算；未配置时返回 0。"""
    price = pricing.get(model) or {}
    if not price and str(model).startswith("deepseek"):
        # 兼容 API 响应名与配置名不一致：deepseek-flash / deepseek-chat 共用一档。
        price = pricing.get("deepseek-chat") or pricing.get("deepseek-flash") or {}
    if not isinstance(price, dict):
        return 0.0
    return (
        prompt_tokens / 1_000_000 * _number(price.get("input_per_1m"))
        + completion_tokens / 1_000_000 * _number(price.get("output_per_1m"))
    )


def load_events(trace_dir: Path) -> list[dict]:
    """读取所有 trace 文件；坏行跳过，不影响报告。"""
    events: list[dict] = []
    for path in sorted(Path(trace_dir).glob("trace_*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                events.append(item)
    return events


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _timestamp(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _run_duration(events: list[dict], run_end: dict | None) -> int | None:
    if run_end:
        duration = run_end.get("duration_ms")
        if duration is not None:
            return _int(duration)
    stamps = [_timestamp(event.get("ts")) for event in events]
    stamps = [stamp for stamp in stamps if stamp is not None]
    if len(stamps) < 2:
        return None
    return max(int((max(stamps) - min(stamps)).total_seconds() * 1000), 0)


def _ts_ms(value: Any) -> float | None:
    stamp = _timestamp(value)
    return stamp.timestamp() * 1000 if stamp is not None else None


def _merge_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """合并重叠/相邻的时间区间，用于避免嵌套调用重复计时。"""
    if not intervals:
        return []
    ordered = sorted((start, end) for start, end in intervals if end > start)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _union_ms(intervals: list[tuple[float, float]]) -> float:
    return sum(end - start for start, end in _merge_intervals(intervals))


def _intersection_ms(left: list[tuple[float, float]], right: list[tuple[float, float]]) -> float:
    """两个区间集合的交集长度；嵌套模型调用会落在这里。"""
    a = _merge_intervals(left)
    b = _merge_intervals(right)
    total = 0.0
    i = j = 0
    while i < len(a) and j < len(b):
        start = max(a[i][0], b[j][0])
        end = min(a[i][1], b[j][1])
        if end > start:
            total += end - start
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return total


def _clamp_interval(
    interval: tuple[float, float],
    start: float | None,
    end: float | None,
) -> tuple[float, float] | None:
    left, right = interval
    if start is not None:
        left = max(left, start)
    if end is not None:
        right = min(right, end)
    return (left, right) if right > left else None


def _span_intervals(
    rows: list[dict],
    start_event: str,
    end_event: str,
    error_event: str,
    run_start: float | None,
    run_end: float | None,
) -> tuple[list[tuple[float, float]], dict[str, float], dict[str, int]]:
    """从 start/end/error 事件重建时间区间。

    返回 ``(intervals, ms_by_name, calls_by_name)``；区间已按 run 窗口裁剪。
    """
    starts: dict[str, float] = {}
    names: dict[str, str] = {}
    intervals: list[tuple[float, float]] = []
    by_name: dict[str, float] = defaultdict(float)
    calls: dict[str, int] = defaultdict(int)

    for row in rows:
        event = row.get("event")
        run_id = str(row.get("run_id") or "")
        if event == start_event:
            stamp = _ts_ms(row.get("ts"))
            if stamp is not None:
                starts[run_id] = stamp
            names[run_id] = str(row.get("model") or row.get("tool") or "unknown")
        elif event == end_event:
            end = _ts_ms(row.get("ts"))
            start = starts.pop(run_id, None)
            latency = row.get("latency_ms")
            if end is not None and latency is not None:
                start = end - _number(latency)
            if start is None and end is not None:
                start = end - _number(latency)
            if start is None or end is None:
                continue
            name = str(row.get("model") or row.get("tool") or names.get(run_id) or "unknown")
            interval = _clamp_interval((start, end), run_start, run_end)
            if interval:
                intervals.append(interval)
                by_name[name] += interval[1] - interval[0]
                calls[name] += 1
            names.pop(run_id, None)
        elif event == error_event:
            end = _ts_ms(row.get("ts"))
            start = starts.pop(run_id, None)
            if start is None or end is None:
                continue
            name = str(row.get("model") or row.get("tool") or names.get(run_id) or "unknown")
            interval = _clamp_interval((start, end), run_start, run_end)
            if interval:
                intervals.append(interval)
                by_name[name] += interval[1] - interval[0]
                calls[name] += 1
            names.pop(run_id, None)

    # 未闭合的 start（例如 HITL 中断）按 run 结束时间收口，避免完全丢失。
    for run_id, start in starts.items():
        if run_end is None:
            continue
        name = names.get(run_id) or "unknown"
        interval = _clamp_interval((start, run_end), run_start, run_end)
        if interval:
            intervals.append(interval)
            by_name[name] += interval[1] - interval[0]
            calls[name] += 1

    return intervals, dict(by_name), dict(calls)


def _latency_breakdown(
    model_intervals: list[tuple[float, float]],
    tool_intervals: list[tuple[float, float]],
    total_ms: int | None,
) -> dict | None:
    """把 wall-clock 拆成 模型 / 工具 / 重叠 / 其他。"""
    if total_ms is None or total_ms <= 0:
        return None
    model_union = _union_ms(model_intervals)
    tool_union = _union_ms(tool_intervals)
    overlap = _intersection_ms(model_intervals, tool_intervals)
    active = _union_ms(model_intervals + tool_intervals)
    model_only = max(model_union - overlap, 0.0)
    tool_only = max(tool_union - overlap, 0.0)
    other = max(float(total_ms) - active, 0.0)
    return {
        "total_ms": float(total_ms),
        "model_ms": round(model_only, 1),
        "tool_ms": round(tool_only, 1),
        "overlap_ms": round(overlap, 1),
        "other_ms": round(other, 1),
    }


def group_runs(events: Iterable[dict], pricing: dict | None = None) -> list[dict]:
    """按 trace_id 聚合一次 run；同时保留模型名、工具次数和错误。

    成本优先用当前配置单价重算，保证旧 trace 在补价格后也能得到估算值；
    未配置单价时回退到 trace 中记录的 cost_est。
    """
    pricing = pricing or {}
    grouped: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        trace_id = event.get("trace_id")
        if trace_id:
            grouped[str(trace_id)].append(event)

    runs: list[dict] = []
    for trace_id, rows in grouped.items():
        rows.sort(key=lambda item: str(item.get("ts", "")))
        model_ends = [row for row in rows if row.get("event") == "model_end"]
        tool_ends = [row for row in rows if row.get("event") == "tool_end"]
        model_starts = [row for row in rows if row.get("event") == "model_start"]
        run_end = next((row for row in reversed(rows) if row.get("event") == "run_end"), None)
        # 成功的 model_end 优先；模型调用失败（只有 model_start + model_error）时
        # 用 model_start 的模型名，避免整个 run 掉进 unknown 桶。
        models = sorted({
            str(row.get("model") or "unknown")
            for row in model_ends
            if row.get("model")
        }) or sorted({
            str(row.get("model") or "unknown")
            for row in model_starts
            if row.get("model")
        }) or ["unknown"]
        scenario = next(
            (str(row.get("scenario")) for row in rows if row.get("scenario")),
            None,
        )
        duration = _run_duration(rows, run_end)
        run_end_ts = _ts_ms((run_end or {}).get("ts"))
        run_start = (
            run_end_ts - duration
            if run_end_ts is not None and duration is not None
            else None
        )
        model_intervals, model_latency, model_latency_calls = _span_intervals(
            rows, "model_start", "model_end", "model_error", run_start, run_end_ts
        )
        tool_intervals, tool_latency, tool_latency_calls = _span_intervals(
            rows, "tool_start", "tool_end", "tool_error", run_start, run_end_ts
        )
        latency_breakdown = _latency_breakdown(model_intervals, tool_intervals, duration)
        tokens = sum(_int(row.get("total_tokens")) for row in model_ends)
        prompt_tokens = sum(_int(row.get("prompt_tokens")) for row in model_ends)
        completion_tokens = sum(_int(row.get("completion_tokens")) for row in model_ends)
        recorded_cost = sum(_number(row.get("cost_est")) for row in model_ends)
        if pricing:
            cost = sum(
                estimate_cost(
                    str(row.get("model") or "unknown"),
                    _int(row.get("prompt_tokens")),
                    _int(row.get("completion_tokens")),
                    pricing,
                )
                for row in model_ends
            )
        else:
            cost = recorded_cost
        errors = [
            f"{row.get('event')}: {row.get('error', '')}"
            for row in rows
            if row.get("event") in {"model_error", "tool_error"}
        ]
        if run_end and run_end.get("error"):
            errors.append(str(run_end["error"]))

        # run_end 的汇总值优先；旧 trace 没有 run_end 时用逐事件累加值。
        if run_end:
            tokens = _int(run_end.get("total_tokens"), tokens)
            prompt_tokens = _int(run_end.get("prompt_tokens"), prompt_tokens)
            completion_tokens = _int(run_end.get("completion_tokens"), completion_tokens)
            if not pricing:
                cost = _number(run_end.get("cost_est"), cost)

        runs.append({
            "trace_id": trace_id,
            "thread_id": next((row.get("thread_id") for row in rows if row.get("thread_id")), None),
            "scenario": scenario,
            "status": str((run_end or {}).get("status") or "unknown"),
            "model": ", ".join(models) if models else "unknown",
            "models": models,
            "model_calls": _int((run_end or {}).get("model_calls"), len(model_ends)),
            "tool_calls": _int((run_end or {}).get("tool_calls"), len(tool_ends)),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": tokens,
            "cost_est": round(cost, 6),
            "duration_ms": duration,
            "tools": sorted({
                str(row.get("tool"))
                for row in tool_ends
                if row.get("tool")
            }),
            "errors": errors,
            "has_errors": bool(errors),
            "latency_breakdown": latency_breakdown,
            "model_latency": {name: round(value, 1) for name, value in model_latency.items()},
            "model_latency_calls": model_latency_calls,
            "tool_latency": {name: round(value, 1) for name, value in tool_latency.items()},
            "tool_latency_calls": tool_latency_calls,
            "started_at": rows[0].get("ts") if rows else None,
        })
    return sorted(runs, key=lambda item: str(item.get("started_at") or ""), reverse=True)


def percentile(values: Iterable[float], ratio: float) -> float | None:
    """线性插值百分位；空列表返回 None。"""
    items = sorted(float(value) for value in values)
    if not items:
        return None
    if len(items) == 1:
        return items[0]
    position = (len(items) - 1) * min(max(float(ratio), 0.0), 1.0)
    lower = int(position)
    upper = min(lower + 1, len(items) - 1)
    weight = position - lower
    return items[lower] * (1 - weight) + items[upper] * weight


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def summarize(runs: list[dict]) -> dict:
    completed = [run for run in runs if run["status"] == "completed"]
    failed = [run for run in runs if run["status"] not in {"completed", "unknown"}]
    durations = [run["duration_ms"] for run in runs if run.get("duration_ms") is not None]
    completed_durations = [
        run["duration_ms"] for run in completed if run.get("duration_ms") is not None
    ]
    total_tokens = sum(run["total_tokens"] for run in runs)
    total_cost = sum(run["cost_est"] for run in runs)
    total_duration = sum(durations)
    success_cost = sum(run["cost_est"] for run in completed)

    by_model: dict[str, dict] = {}
    for model in sorted({model for run in runs for model in (run.get("models") or ["unknown"])}):
        subset = [run for run in runs if model in (run.get("models") or ["unknown"])]
        model_durations = [
            run["duration_ms"] for run in subset if run.get("duration_ms") is not None
        ]
        by_model[model] = {
            "runs": len(subset),
            "completed": sum(1 for run in subset if run["status"] == "completed"),
            "errors": sum(1 for run in subset if run.get("has_errors")),
            "tokens": sum(run["total_tokens"] for run in subset),
            "cost_est": round(sum(run["cost_est"] for run in subset), 6),
            "p50_ms": percentile(model_durations, 0.50),
            "p95_ms": percentile(model_durations, 0.95),
        }

    tool_counts = Counter(
        tool for run in runs for tool in (run.get("tools") or [])
    )
    scenario_counts = Counter(
        run.get("scenario") or "unknown" for run in runs
    )

    error_runs = sum(1 for run in runs if run.get("has_errors"))
    model_error_runs = sum(
        1
        for run in runs
        if any(str(item).startswith("model_error") for item in (run.get("errors") or []))
    )

    # wall-clock 拆解：模型 / 工具 / 模型-工具重叠 / 其他编排。
    breakdowns = [
        run["latency_breakdown"]
        for run in runs
        if isinstance(run.get("latency_breakdown"), dict)
    ]
    total_breakdown = sum(item.get("total_ms", 0.0) for item in breakdowns)
    model_ms = sum(item.get("model_ms", 0.0) for item in breakdowns)
    tool_ms = sum(item.get("tool_ms", 0.0) for item in breakdowns)
    overlap_ms = sum(item.get("overlap_ms", 0.0) for item in breakdowns)
    other_ms = sum(item.get("other_ms", 0.0) for item in breakdowns)

    def _bucket_pct(value: float) -> float:
        return round(value / total_breakdown, 4) if total_breakdown else 0.0

    latency_breakdown = {
        "runs": len(breakdowns),
        "total_ms": round(total_breakdown, 1),
        "model_ms": round(model_ms, 1),
        "tool_ms": round(tool_ms, 1),
        "overlap_ms": round(overlap_ms, 1),
        "other_ms": round(other_ms, 1),
        "model_pct": _bucket_pct(model_ms),
        "tool_pct": _bucket_pct(tool_ms),
        "overlap_pct": _bucket_pct(overlap_ms),
        "other_pct": _bucket_pct(other_ms),
        "model_p50_ms": percentile([item.get("model_ms", 0.0) for item in breakdowns], 0.50),
        "model_p95_ms": percentile([item.get("model_ms", 0.0) for item in breakdowns], 0.95),
        "tool_p50_ms": percentile([item.get("tool_ms", 0.0) for item in breakdowns], 0.50),
        "tool_p95_ms": percentile([item.get("tool_ms", 0.0) for item in breakdowns], 0.95),
        "other_p50_ms": percentile([item.get("other_ms", 0.0) for item in breakdowns], 0.50),
        "other_p95_ms": percentile([item.get("other_ms", 0.0) for item in breakdowns], 0.95),
    }

    model_latency: dict[str, float] = defaultdict(float)
    model_latency_calls: Counter = Counter()
    for run in runs:
        for name, value in (run.get("model_latency") or {}).items():
            model_latency[name] += _number(value)
            model_latency_calls[name] += _int((run.get("model_latency_calls") or {}).get(name))
    by_model_latency = {
        name: {"ms": round(value, 1), "calls": model_latency_calls[name]}
        for name, value in sorted(model_latency.items(), key=lambda pair: -pair[1])
    }

    tool_latency: dict[str, float] = defaultdict(float)
    tool_latency_calls: Counter = Counter()
    for run in runs:
        for name, value in (run.get("tool_latency") or {}).items():
            tool_latency[name] += _number(value)
            tool_latency_calls[name] += _int((run.get("tool_latency_calls") or {}).get(name))
    by_tool_latency = {
        name: {"ms": round(value, 1), "calls": tool_latency_calls[name]}
        for name, value in sorted(tool_latency.items(), key=lambda pair: -pair[1])
    }

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "runs": len(runs),
        "completed": len(completed),
        "failed": len(failed),
        "unknown": sum(1 for run in runs if run["status"] == "unknown"),
        "error_runs": error_runs,
        "model_error_runs": model_error_runs,
        "success_rate": _rate(len(completed), len(runs)),
        "duration_total_ms": total_duration,
        "duration_p50_ms": percentile(durations, 0.50),
        "duration_p95_ms": percentile(durations, 0.95),
        "completed_duration_p50_ms": percentile(completed_durations, 0.50),
        "completed_duration_p95_ms": percentile(completed_durations, 0.95),
        "model_calls": sum(run["model_calls"] for run in runs),
        "tool_calls": sum(run["tool_calls"] for run in runs),
        "prompt_tokens": sum(run["prompt_tokens"] for run in runs),
        "completion_tokens": sum(run["completion_tokens"] for run in runs),
        "total_tokens": total_tokens,
        "avg_tokens": round(total_tokens / len(runs), 1) if runs else 0.0,
        "cost_est": round(total_cost, 6),
        "avg_cost": round(total_cost / len(runs), 6) if runs else 0.0,
        "cost_per_success": round(success_cost / len(completed), 6) if completed else 0.0,
        "pricing_configured": total_cost > 0,
        "by_model": by_model,
        "by_tool": dict(tool_counts.most_common()),
        "by_scenario": dict(scenario_counts.most_common()),
        "latency_breakdown": latency_breakdown,
        "by_model_latency": by_model_latency,
        "by_tool_latency": by_tool_latency,
    }


def _fmt_ms(value: float | None) -> str:
    if value is None:
        return "—"
    if value >= 1000:
        return f"{value / 1000:.2f}s"
    return f"{value:.0f}ms"


def _fmt_duration(value: float | None) -> str:
    """累计时延用分钟/小时，避免 10362.56s。"""
    if value is None:
        return "—"
    if value >= 3_600_000:
        return f"{value / 3_600_000:.2f}h"
    if value >= 60_000:
        return f"{value / 60_000:.1f}min"
    return _fmt_ms(value)


def _fmt_int(value: Any) -> str:
    return f"{_int(value):,}"


def _fmt_cost(value: Any) -> str:
    return f"¥{_number(value):.4f}"


def write_markdown(path: Path, report: dict) -> None:
    summary = report["summary"]
    lines = [
        "# Agent 成本 / 时延报告",
        "",
        f"> 生成时间：{summary['generated_at']}",
        "> 数据来源：`outputs/traces/trace_*.jsonl`；不调用模型，只聚合已有 trace。",
        "",
        "## 1. 总览",
        "",
        "| 指标 | 数值 |",
        "|:---|:---:|",
        f"| Run 数 | {summary['runs']} |",
        f"| 成功 / 失败 / 未知 | {summary['completed']} / {summary['failed']} / {summary['unknown']} |",
        f"| 含错误 run（model_error / tool_error） | {summary.get('error_runs', 0)} |",
        f"| 成功率 | {summary['success_rate']:.1%} |",
        f"| 延迟 p50 / p95 | {_fmt_ms(summary['duration_p50_ms'])} / {_fmt_ms(summary['duration_p95_ms'])} |",
        f"| 完成 run 延迟 p50 / p95 | {_fmt_ms(summary['completed_duration_p50_ms'])} / "
        f"{_fmt_ms(summary['completed_duration_p95_ms'])} |",
        f"| 模型调用 / 工具调用 | {_fmt_int(summary['model_calls'])} / {_fmt_int(summary['tool_calls'])} |",
        f"| Token（输入 / 输出 / 总计） | {_fmt_int(summary['prompt_tokens'])} / "
        f"{_fmt_int(summary['completion_tokens'])} / {_fmt_int(summary['total_tokens'])} |",
        f"| 平均 Token / run | {summary['avg_tokens']:.1f} |",
        f"| 估算总成本 | {_fmt_cost(summary['cost_est'])} |",
        f"| 平均成本 / run | {_fmt_cost(summary['avg_cost'])} |",
        f"| 每个成功 run 成本 | {_fmt_cost(summary['cost_per_success'])} |",
        "",
    ]
    if not summary["pricing_configured"]:
        lines += [
            "> 注意：`config/observability.yml` 的 `pricing` 为空或未匹配模型，"
            "成本显示为 0；Token 和时延仍然有效。",
            "",
        ]

    lines += [
        "## 2. 按模型",
        "",
        "| 模型 | Run | 成功 | 错误 | Token | 估算成本 | p50 | p95 |",
        "|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]
    for model, item in summary["by_model"].items():
        lines.append(
            f"| {model} | {item['runs']} | {item['completed']} | {item.get('errors', 0)} | "
            f"{_fmt_int(item['tokens'])} | {_fmt_cost(item['cost_est'])} | "
            f"{_fmt_ms(item['p50_ms'])} | {_fmt_ms(item['p95_ms'])} |"
        )

    lines += [
        "",
        "## 3. 工具与场景",
        "",
        f"- 工具调用分布：`{summary['by_tool'] or {}}`",
        f"- 场景分布：`{summary['by_scenario'] or {}}`",
        "",
        "## 4. 时延拆解",
        "",
        "> wall-clock 拆解：模型 / 工具按事件区间合并；`工具内模型/重叠` 是工具内部发生的模型调用；`其他/编排` 是中间件、checkpoint、排队、未埋点等。",
        "",
        "| 部分 | 累计 | 占比 | p50 | p95 |",
        "|:---|:---:|:---:|:---:|:---:|",
    ]
    breakdown = summary.get("latency_breakdown") or {}
    lines += [
        f"| 模型调用 | {_fmt_duration(breakdown.get('model_ms'))} | "
        f"{_number(breakdown.get('model_pct')):.1%} | "
        f"{_fmt_ms(breakdown.get('model_p50_ms'))} | {_fmt_ms(breakdown.get('model_p95_ms'))} |",
        f"| 工具调用 | {_fmt_duration(breakdown.get('tool_ms'))} | "
        f"{_number(breakdown.get('tool_pct')):.1%} | "
        f"{_fmt_ms(breakdown.get('tool_p50_ms'))} | {_fmt_ms(breakdown.get('tool_p95_ms'))} |",
        f"| 工具内模型 / 重叠 | {_fmt_duration(breakdown.get('overlap_ms'))} | "
        f"{_number(breakdown.get('overlap_pct')):.1%} | — | — |",
        f"| 其他 / 编排 | {_fmt_duration(breakdown.get('other_ms'))} | "
        f"{_number(breakdown.get('other_pct')):.1%} | "
        f"{_fmt_ms(breakdown.get('other_p50_ms'))} | {_fmt_ms(breakdown.get('other_p95_ms'))} |",
        "",
        "### 按工具时延",
        "",
        "| 工具 | 累计时延 | 调用次数 |",
        "|:---|:---:|:---:|",
    ]
    for name, item in (summary.get("by_tool_latency") or {}).items():
        lines.append(f"| {name} | {_fmt_duration(item.get('ms'))} | {_fmt_int(item.get('calls'))} |")
    lines += [
        "",
        "### 按模型时延",
        "",
        "| 模型 | 累计时延 | 调用次数 |",
        "|:---|:---:|:---:|",
    ]
    for name, item in (summary.get("by_model_latency") or {}).items():
        lines.append(f"| {name} | {_fmt_duration(item.get('ms'))} | {_fmt_int(item.get('calls'))} |")

    lines += [
        "",
        "## 5. 最近 Run",
        "",
        "| Trace | 场景 | 状态 | 模型 | 模型/工具 | Token | 成本 | 延迟 |",
        "|:---|:---|:---:|:---|:---:|:---:|:---:|:---:|",
    ]
    for run in report["runs"][:30]:
        lines.append(
            f"| `{run['trace_id']}` | {run.get('scenario') or '—'} | {run['status']} | "
            f"{run.get('model') or '—'} | {run['model_calls']}/{run['tool_calls']} | "
            f"{_fmt_int(run['total_tokens'])} | {_fmt_cost(run['cost_est'])} | "
            f"{_fmt_ms(run.get('duration_ms'))} |"
        )

    lines += [
        "",
        "## 6. 口径",
        "",
        "- 成功率只统计 `run_end.status == completed`；`unknown` 是旧版 trace 没有 run_end 兜底。",
        "- 含错误 run 是 trace 中出现 `model_error` / `tool_error` 的 run；其中可能有 `run_end.status=completed` 的兜底回复。",
        "- 时延拆解来自 `model_start/model_end`、`tool_start/tool_end` 的 `ts` + `latency_ms`；区间合并后避免嵌套调用重复计时。",
        "- 模型调用失败时，`model_start -> model_error` 的耗时计入模型时延；`by_model` 优先用成功的 `model_end`，失败 run 回退到 `model_start` 的模型名。",
        "- p50 / p95 按 run 的 `duration_ms` 计算；完成 run 的 p50 / p95 单独列出，避免错误 run 拉低。",
        "- 成本按 `config/observability.yml` 的每百万 token 单价估算，不等于账单。",
        "- 这是本地 trace 聚合，不是生产监控；没有并发、排队、网络重试等独立维度。",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_report(trace_dir: Path = DEFAULT_TRACE_DIR, pricing: dict | None = None) -> dict:
    pricing = load_pricing() if pricing is None else pricing
    runs = group_runs(load_events(trace_dir), pricing=pricing)
    summary = summarize(runs)
    summary["pricing"] = pricing
    return {"summary": summary, "runs": runs}


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description="聚合本地 trace，生成成本 / 时延报告")
    parser.add_argument("--trace-dir", default=str(DEFAULT_TRACE_DIR))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    args = parser.parse_args(argv)

    report = build_report(Path(args.trace_dir))
    out_path = Path(args.out)
    json_path = Path(args.json_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_markdown(out_path, report)

    summary = report["summary"]
    print(f"runs={summary['runs']} success={summary['success_rate']:.1%} "
          f"p95={_fmt_ms(summary['duration_p95_ms'])} "
          f"tokens={summary['total_tokens']} cost={_fmt_cost(summary['cost_est'])}")
    print(f"report: {out_path}")
    print(f"details: {json_path}")
    return report


if __name__ == "__main__":
    main()
