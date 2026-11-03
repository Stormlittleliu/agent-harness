# -*- coding: utf-8 -*-
"""Planning Policy A/B 实验：baseline（模型自主路由）vs policy（确定性注入）。

指标：
- target accuracy：最终调用的 route_to_* 是否指向正确场景；
- abstain rate：policy 认为规则不唯一时交回模型的比例；
- 平均时延、模型调用次数、token；
- planned_correct：policy 的规划本身是否正确（只对 policy 变体有意义）。

用法：
    python -m core.experiments.planner_eval --trials 1
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.messages import AIMessage  # noqa: E402

from core.agent.framework import FrameworkAgent  # noqa: E402
from core.agent.middleware import classify_intent  # noqa: E402
from core.quality.agent_eval import extract_final_answer, extract_tool_calls  # noqa: E402
from core.quality.paths import OUTPUTS_DIR  # noqa: E402
from core.scenarios.registry import get_scenario  # noqa: E402
from core.scenarios.router.scenario import ROUTER_POLICY  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

OUT_DIR = OUTPUTS_DIR / "experiments"

TOOL_TARGETS = {
    "route_to_workspace": "workspace_assistant",
    "route_to_coding": "coding_demo",
    "route_to_robot": "robot_vacuum",
    "route_to_research": "research_assistant",
}

PROMPTS = [
    ("根据笔记帮我整理一份 Agent 评测的学习计划。", "workspace_assistant"),
    ("把这段英文总结成中文：The agent harness provides tools and evaluation.", "workspace_assistant"),
    ("请记住：我喜欢简洁的回答，并用要点列出。", "workspace_assistant"),
    ("帮我把会议记录整理成待办清单。", "workspace_assistant"),
    ("写一个输出 99 乘法表的 Python 脚本并运行验证。", "coding_demo"),
    ("这个 Python 脚本报错了，帮我调试一下。", "coding_demo"),
    ("扫地机器人回充失败怎么办？", "robot_vacuum"),
    ("扫地机器人滤网多久换一次？", "robot_vacuum"),
    ("对比三份资料，告诉我它们对 Agent 评测的主要差异。", "research_assistant"),
    ("帮我调研多 Agent 协作的主要风险，并给出来源。", "research_assistant"),
    ("Summarize the product brief in Chinese and list the user scenarios.", "workspace_assistant"),
    ("把 'The agent harness provides tools and evaluation' 翻译成中文。", "workspace_assistant"),
]


def _model_calls(messages) -> int:
    """统计真实模型调用：排除 policy 注入的合成 AIMessage。"""
    count = 0
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        calls = getattr(message, "tool_calls", None) or []
        if calls and all(str(call.get("id", "")).startswith("policy-") for call in calls):
            continue
        count += 1
    return count


def _tokens(messages) -> int:
    total = 0
    for message in messages:
        usage = getattr(message, "usage_metadata", None) or {}
        total += int(usage.get("total_tokens", 0) or 0)
    return total


def _selected_target(tool_names: list[str]) -> str | None:
    targets = [TOOL_TARGETS[name] for name in tool_names if name in TOOL_TARGETS]
    return targets[-1] if targets else None


def run_variant(name: str, trials: int) -> list[dict]:
    scenario = get_scenario("router")
    scenario = replace(
        scenario,
        name=f"router_{name}",
        planning_policy=None if name == "baseline" else ROUTER_POLICY,
        checkpoint=False,
    )
    agent = FrameworkAgent(scenario)
    rows = []
    for trial in range(1, trials + 1):
        for index, (prompt, expected) in enumerate(PROMPTS, 1):
            started = time.perf_counter()
            final_state = agent.invoke(prompt)
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            messages = final_state.get("messages", [])
            tool_names = [item["name"] for item in extract_tool_calls(messages) if item.get("name")]
            selected = _selected_target(tool_names)
            plan = classify_intent(prompt, ROUTER_POLICY) if name == "policy" else None
            planned_tool = plan.tool if plan else None
            planned_target = TOOL_TARGETS.get(planned_tool) if planned_tool else None
            row = {
                "variant": name,
                "trial": trial,
                "index": index,
                "prompt": prompt,
                "expected": expected,
                "selected_target": selected,
                "selected_tool": next(
                    (tool for tool in reversed(tool_names) if tool in TOOL_TARGETS), None
                ),
                "correct": selected == expected,
                "abstained": name == "policy" and plan is None,
                "planned_tool": planned_tool,
                "planned_target": planned_target,
                "planned_correct": planned_target == expected if planned_target else None,
                "latency_ms": latency_ms,
                "model_calls": _model_calls(messages),
                "tool_calls": len(tool_names),
                "tokens": _tokens(messages),
                "answer": extract_final_answer(messages)[:200],
            }
            rows.append(row)
            print(
                f"[{name} {trial}/{trials} {index}/{len(PROMPTS)}] "
                f"expected={expected} selected={selected} correct={row['correct']} "
                f"planned={planned_target} abstain={row['abstained']} "
                f"models={row['model_calls']} latency={latency_ms:.0f}ms"
            )
    return rows


def summarize(rows: list[dict]) -> dict:
    total = len(rows)
    correct = sum(1 for row in rows if row["correct"])
    planned = [row for row in rows if row.get("planned_target")]
    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "abstained": sum(1 for row in rows if row["abstained"]),
        "abstain_rate": round(sum(1 for row in rows if row["abstained"]) / total, 4) if total else 0.0,
        "planned_correct": sum(1 for row in planned if row["planned_correct"]),
        "planned_total": len(planned),
        "avg_latency_ms": round(sum(row["latency_ms"] for row in rows) / total, 1) if total else 0.0,
        "avg_model_calls": round(sum(row["model_calls"] for row in rows) / total, 2) if total else 0.0,
        "avg_tokens": round(sum(row["tokens"] for row in rows) / total, 1) if total else 0.0,
    }


def write_markdown(path: Path, summaries: dict, rows: list[dict]) -> None:
    lines = [
        "# Planning Policy A/B 实验",
        "",
        f"> 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "> baseline = 模型自主路由；policy = 确定性注入 route_to_*，不命中/平局 abstain。",
        "",
        "## 总览",
        "",
        "| 变体 | 样本 | 正确 | 准确率 | abstain | 平均时延 | 平均模型调用 | 平均 token |",
        "|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|",
    ]
    for name, item in summaries.items():
        lines.append(
            f"| {name} | {item['total']} | {item['correct']} | {item['accuracy']:.1%} | "
            f"{item['abstained']} ({item['abstain_rate']:.0%}) | {item['avg_latency_ms']:.0f}ms | "
            f"{item['avg_model_calls']:.1f} | {item['avg_tokens']:.0f} |"
        )

    for name, item in summaries.items():
        lines += [
            "",
            f"## {name}",
            "",
            "| # | 问题 | 期望 | 实际 | 正确 | 规划 | abstain | 模型调用 | 时延 |",
            "|:---:|:---|:---|:---|:---:|:---|:---:|:---:|:---:|",
        ]
        for row in rows:
            if row["variant"] != name:
                continue
            lines.append(
                f"| {row['index']} | {row['prompt'][:40]} | {row['expected']} | "
                f"{row['selected_target'] or '-'} | {'✅' if row['correct'] else '❌'} | "
                f"{row['planned_target'] or '-'} | {'是' if row['abstained'] else '否'} | "
                f"{row['model_calls']} | {row['latency_ms']:.0f}ms |"
            )

    lines += [
        "",
        "## 口径",
        "",
        "- baseline 不用 policy，完全由模型决定是否调用 route_to_*。",
        "- policy 只在规则唯一命中时注入工具调用；平局/无命中 abstain，交回模型。",
        "- 这是 12 条小样本行为实验，不是统计显著结论；准确率以实际路由目标为准。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(trials: int = 1) -> dict:
    rows = []
    summaries = {}
    for name in ("baseline", "policy"):
        variant_rows = run_variant(name, trials)
        rows.extend(variant_rows)
        summaries[name] = summarize(variant_rows)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = OUT_DIR / f"planner_eval_{stamp}.json"
    md_path = OUT_DIR / f"planner_eval_{stamp}.md"
    payload = {"summaries": summaries, "results": rows}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(md_path, summaries, rows)

    print("\n=== summary ===")
    print(json.dumps(summaries, ensure_ascii=False, indent=2))
    print(f"\nreport: {md_path}")
    print(f"details: {json_path}")
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description="Planning Policy A/B 实验")
    parser.add_argument("--trials", type=int, default=1)
    args = parser.parse_args(argv)
    run(trials=max(1, args.trials))


if __name__ == "__main__":
    main()
