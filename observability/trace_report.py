# -*- coding: utf-8 -*-
"""查看本地 trace。

用法：
    python test_entry.py trace --last 10
    python test_entry.py trace --trace-id run-xxxx
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "logs" / "traces"


def load_events(trace_dir: Path) -> list[dict]:
    events = []
    for path in sorted(trace_dir.glob("trace_*.jsonl")):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def summarize(events: list[dict]) -> list[dict]:
    runs: dict[str, dict] = {}
    for event in events:
        trace_id = event.get("trace_id")
        if not trace_id:
            continue
        run = runs.setdefault(trace_id, {
            "trace_id": trace_id,
            "thread_id": event.get("thread_id"),
            "status": "running",
            "model_calls": 0,
            "tool_calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost_est": 0.0,
            "duration_ms": None,
            "first_ts": event.get("ts", ""),
            "last_ts": event.get("ts", ""),
            "tools": [],
            "errors": [],
        })
        run["last_ts"] = event.get("ts", run["last_ts"])
        name = event.get("event")

        if name == "model_end":
            run["model_calls"] += 1
            run["prompt_tokens"] += int(event.get("prompt_tokens") or 0)
            run["completion_tokens"] += int(event.get("completion_tokens") or 0)
            run["total_tokens"] += int(event.get("total_tokens") or 0)
            run["cost_est"] += float(event.get("cost_est") or 0)
        elif name == "tool_end":
            run["tool_calls"] += 1
            tool = event.get("tool")
            if tool and tool not in run["tools"]:
                run["tools"].append(tool)
        elif name in {"model_error", "tool_error"}:
            run["errors"].append(f"{name}: {event.get('error', '')}")
        elif name == "run_end":
            run["status"] = event.get("status", "completed")
            run["model_calls"] = int(event.get("model_calls") or run["model_calls"])
            run["tool_calls"] = int(event.get("tool_calls") or run["tool_calls"])
            run["prompt_tokens"] = int(event.get("prompt_tokens") or run["prompt_tokens"])
            run["completion_tokens"] = int(event.get("completion_tokens") or run["completion_tokens"])
            run["total_tokens"] = int(event.get("total_tokens") or run["total_tokens"])
            run["cost_est"] = float(event.get("cost_est") or run["cost_est"])
            run["duration_ms"] = event.get("duration_ms")
            if event.get("error"):
                run["errors"].append(str(event["error"]))
    return sorted(runs.values(), key=lambda item: item["last_ts"], reverse=True)


def print_runs(runs: list[dict], limit: int) -> None:
    if not runs:
        print("没有找到 trace；先跑一次 Agent 或测试。")
        return
    print(f"最近 {min(limit, len(runs))} 条 trace：\n")
    print(f"{'trace_id':<34} {'thread_id':<22} {'status':<12} {'model':>5} {'tool':>4} "
          f"{'tokens(in/out)':>16} {'cost':>8} {'duration':>9}")
    for run in runs[:limit]:
        tokens = f"{run['prompt_tokens']}/{run['completion_tokens']}"
        duration = f"{run['duration_ms'] / 1000:.1f}s" if run["duration_ms"] else "-"
        print(f"{run['trace_id']:<34} {str(run['thread_id'])[:21]:<22} {run['status']:<12} "
              f"{run['model_calls']:>5} {run['tool_calls']:>4} {tokens:>16} "
              f"{run['cost_est']:>8.4f} {duration:>9}")


def print_trace(events: list[dict], trace_id: str) -> None:
    rows = [event for event in events if event.get("trace_id") == trace_id]
    if not rows:
        print(f"没有找到 trace：{trace_id}")
        return
    for event in rows:
        event_name = event.get("event")
        detail = ""
        if event_name == "model_end":
            detail = (f"model={event.get('model')} latency={event.get('latency_ms')}ms "
                      f"tokens={event.get('prompt_tokens')}/{event.get('completion_tokens')}")
        elif event_name in {"tool_start", "tool_end", "tool_error"}:
            detail = f"tool={event.get('tool')} {event.get('status') or event.get('error') or ''}"
        elif event_name == "run_end":
            detail = (f"status={event.get('status')} duration={event.get('duration_ms')}ms "
                      f"models={event.get('model_calls')} tools={event.get('tool_calls')} "
                      f"tokens={event.get('prompt_tokens')}/{event.get('completion_tokens')}")
        print(f"{event.get('ts')}  {event_name:<12} {detail}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="查看本地 Agent trace")
    parser.add_argument("--last", type=int, default=10, help="显示最近 N 条，默认 10")
    parser.add_argument("--trace-id", help="显示某条 trace 的完整事件")
    parser.add_argument("--dir", default=str(DEFAULT_DIR), help="trace 目录")
    args = parser.parse_args(argv)

    events = load_events(Path(args.dir))
    if args.trace_id:
        print_trace(events, args.trace_id)
    else:
        print_runs(summarize(events), args.last)


if __name__ == "__main__":
    main()
