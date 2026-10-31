# -*- coding: utf-8 -*-
"""BFCL v4 工具调用评测（simple_python + irrelevance）。

用 DeepSeek 的 OpenAI 兼容 tool calling 跑 BFCL 公开数据，统计：
- 函数选择准确率
- 参数正确率
- 端到端 exact match
- 无关工具误调用率（irrelevance）

说明：这是抽样评测，不是 BFCL 官方完整榜单；评分逻辑为简化版。
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.messages import HumanMessage  # noqa: E402

from core.quality.paths import BFCL_OUT  # noqa: E402
from core.llm.factory import chat_model  # noqa: E402

BFCL_DATA = Path(r"E:\CODE\benchmarks\BFCL\berkeley-function-call-leaderboard\bfcl_eval\data")
SIMPLE = BFCL_DATA / "BFCL_v4_simple_python.json"
SIMPLE_GT = BFCL_DATA / "possible_answer" / "BFCL_v4_simple_python.json"
IRRELEVANCE = BFCL_DATA / "BFCL_v4_irrelevance.json"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


def read_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def first_user_text(item) -> str:
    parts = []
    for turn in item.get("question", []):
        for msg in turn:
            if msg.get("role") == "user":
                parts.append(msg.get("content", ""))
    return "\n".join(parts)


def normalize_schema(schema):
    if not isinstance(schema, dict):
        return schema
    schema = dict(schema)
    t = schema.get("type")
    if t == "dict":
        schema["type"] = "object"
    elif t in ("list", "tuple"):
        schema["type"] = "array"
    elif t == "float":
        schema["type"] = "number"
    elif t == "any":
        schema.pop("type", None)
    if "properties" in schema and isinstance(schema["properties"], dict):
        schema["properties"] = {
            key: normalize_schema(value) for key, value in schema["properties"].items()
        }
    if "items" in schema:
        schema["items"] = normalize_schema(schema["items"])
    return schema


def safe_tool_name(name: str) -> str:
    """DeepSeek/OpenAI 工具名只允许字母、数字、下划线、连字符；把点号等替换掉。"""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", str(name)) or "tool"


def to_openai_tools(functions):
    tools = []
    name_map = {}
    used = set()
    for fn in functions or []:
        original = fn.get("name", "")
        safe = safe_tool_name(original)
        base = safe
        suffix = 2
        while safe in used:
            safe = f"{base}_{suffix}"
            suffix += 1
        used.add(safe)
        name_map[safe] = original
        tools.append({
            "type": "function",
            "function": {
                "name": safe,
                "description": fn.get("description", ""),
                "parameters": normalize_schema(fn.get("parameters") or {"type": "object", "properties": {}}),
            },
        })
    return tools, name_map


def norm_value(value):
    if isinstance(value, str):
        return re.sub(r"\s+", "", value).lower()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(float(value), 6)
    if isinstance(value, list):
        return [norm_value(item) for item in value]
    if isinstance(value, dict):
        return {key: norm_value(item) for key, item in value.items()}
    return value


def arg_matches(actual, candidates):
    if not isinstance(candidates, list):
        candidates = [candidates]
    actual_norm = norm_value(actual)
    for candidate in candidates:
        if actual_norm == norm_value(candidate):
            return True
        # BFCL 常用 "" / 0 表示“可省略”
        if candidate in ("", 0, None) and actual in ("", None):
            return True
    return False


def eval_simple(item, expected_calls, tool_calls):
    if not expected_calls:
        return {"name_ok": False, "args_ok": False, "exact": False, "reason": "no ground truth"}
    expected = expected_calls[0]
    expected_name = next(iter(expected.keys()))
    expected_args = expected[expected_name]

    name_ok = len(tool_calls) == 1 and tool_calls[0].get("name") == expected_name
    args_ok = False
    if name_ok:
        actual_args = tool_calls[0].get("args") or {}

        def arg_ok(key, candidates):
            if key in actual_args:
                return arg_matches(actual_args[key], candidates)
            # 可选参数：ground truth 用 "" / 0 / None 表示可省略
            return arg_matches(None, candidates)

        args_ok = all(arg_ok(key, candidates) for key, candidates in expected_args.items())
    return {
        "name_ok": name_ok,
        "args_ok": args_ok,
        "exact": name_ok and args_ok,
        "expected_name": expected_name,
        "expected_args": expected_args,
        "actual": tool_calls,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--simple", type=int, default=100)
    parser.add_argument("--irrelevance", type=int, default=100)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--out-dir", default=str(BFCL_OUT))
    args = parser.parse_args(argv)

    simple_items = list(read_jsonl(SIMPLE))[: args.simple]
    gt = {row["id"]: row.get("ground_truth", []) for row in read_jsonl(SIMPLE_GT)}
    irrelevance_items = list(read_jsonl(IRRELEVANCE))[: args.irrelevance]

    results = []
    total = len(simple_items) + len(irrelevance_items)
    index = 0

    for item in simple_items:
        index += 1
        tools, name_map = to_openai_tools(item.get("function", []))
        question = first_user_text(item)
        try:
            response = chat_model.bind_tools(tools).invoke([HumanMessage(content=question)])
            tool_calls = [
                {"name": name_map.get(call.get("name", ""), call.get("name", "")), "args": call.get("args", {})}
                for call in (response.tool_calls or [])
            ]
            score = eval_simple(item, gt.get(item["id"], []), tool_calls)
            score.update({"id": item["id"], "kind": "simple", "question": question, "error": None})
        except Exception as exc:  # noqa: BLE001
            score = {
                "id": item["id"], "kind": "simple", "question": question,
                "name_ok": False, "args_ok": False, "exact": False,
                "actual": [], "error": f"{type(exc).__name__}: {exc}",
            }
        results.append(score)
        if index % 10 == 0:
            print(f"[{index}/{total}] simple")
        time.sleep(args.delay)

    for item in irrelevance_items:
        index += 1
        tools, name_map = to_openai_tools(item.get("function", []))
        question = first_user_text(item)
        try:
            response = chat_model.bind_tools(tools).invoke([HumanMessage(content=question)])
            tool_calls = [
                {"name": name_map.get(call.get("name", ""), call.get("name", "")), "args": call.get("args", {})}
                for call in (response.tool_calls or [])
            ]
            no_call = len(tool_calls) == 0
            score = {
                "id": item["id"], "kind": "irrelevance", "question": question,
                "no_call": no_call, "actual": tool_calls, "error": None,
            }
        except Exception as exc:  # noqa: BLE001
            score = {
                "id": item["id"], "kind": "irrelevance", "question": question,
                "no_call": False, "actual": [], "error": f"{type(exc).__name__}: {exc}",
            }
        results.append(score)
        if index % 10 == 0:
            print(f"[{index}/{total}]")
        time.sleep(args.delay)

    simple_results = [row for row in results if row["kind"] == "simple"]
    irr_results = [row for row in results if row["kind"] == "irrelevance"]
    summary = {
        "simple_total": len(simple_results),
        "simple_name_ok": sum(1 for row in simple_results if row["name_ok"]),
        "simple_args_ok": sum(1 for row in simple_results if row["args_ok"]),
        "simple_exact": sum(1 for row in simple_results if row["exact"]),
        "irrelevance_total": len(irr_results),
        "irrelevance_no_call": sum(1 for row in irr_results if row["no_call"]),
        "errors": sum(1 for row in results if row.get("error")),
    }
    summary["simple_name_acc"] = round(summary["simple_name_ok"] / len(simple_results), 4) if simple_results else 0.0
    summary["simple_args_acc"] = round(summary["simple_args_ok"] / len(simple_results), 4) if simple_results else 0.0
    summary["simple_exact_acc"] = round(summary["simple_exact"] / len(simple_results), 4) if simple_results else 0.0
    summary["irrelevance_no_call_rate"] = round(summary["irrelevance_no_call"] / len(irr_results), 4) if irr_results else 0.0

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "eval_bfcl.json"
    md_path = out_dir / "eval_bfcl.md"
    json_path.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# BFCL v4 工具调用评测（抽样）",
        "",
        f"- simple_python：{summary['simple_total']} 条",
        f"- irrelevance：{summary['irrelevance_total']} 条",
        f"- 调用错误：{summary['errors']} 条",
        "",
        "| 指标 | 结果 |",
        "|:---|:---:|",
        f"| 函数选择准确率 | {summary['simple_name_acc']:.2%} |",
        f"| 参数正确率 | {summary['simple_args_acc']:.2%} |",
        f"| 端到端 exact | {summary['simple_exact_acc']:.2%} |",
        f"| 无关工具不调用率 | {summary['irrelevance_no_call_rate']:.2%} |",
        "",
        "> 抽样评测，简化评分；不是 BFCL 官方完整榜单。",
        "",
        "## 失败样例",
        "",
        "| ID | 类型 | 期望/实际 | 问题 |",
        "|:---|:---|:---|:---|",
    ]
    for row in results:
        if row["kind"] == "simple" and not row["exact"]:
            lines.append(
                f"| {row['id']} | simple | {row.get('expected_name','')} / "
                f"{row.get('actual')} | {row['question'][:80]} |"
            )
        if row["kind"] == "irrelevance" and not row["no_call"]:
            lines.append(f"| {row['id']} | irrelevance | 不应调用 / {row.get('actual')} | {row['question'][:80]} |")
        if len(lines) > 60:
            break
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("\n=== summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"report: {md_path}")
    print(f"details: {json_path}")


if __name__ == "__main__":
    main()
