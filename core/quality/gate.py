# -*- coding: utf-8 -*-
"""可编程评测门禁：读取已有报告，按阈值断言，回归时 exit 1。

它不是“再跑一遍评测”，而是把评测结果变成 CI 可以执行的检查：
- BFCL：函数选择 / 参数 exact / 无关工具不调用
- 公开 RAG：MultiHop Hit@4
- coding_demo：行为用例通过率
- structured_demo：schema + 内容通过率

用法：
    python -m core.quality.gate
    python -m core.quality.gate --require-all
    python -m core.quality.gate --min-bfcl-exact 0.95 --min-agent 1.0
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

DEFAULT_BFCL = ROOT / "outputs" / "bfcl" / "eval_bfcl.json"
DEFAULT_PUBLIC = ROOT / "outputs" / "public" / "eval_public_results.json"
DEFAULT_AGENT_GLOB = "outputs/agent/agent_test_coding_demo_*.json"
DEFAULT_STRUCTURED_GLOB = "outputs/structured/structured_test_structured_demo_*.json"

DEFAULT_THRESHOLDS = {
    "bfcl_exact": 0.90,
    "bfcl_irrelevance": 0.75,
    "rag_hit4": 0.50,
    "agent_pass": 1.0,
    "structured_pass": 0.80,
    "structured_schema": 1.0,
}


def _number(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _ratio(passed, total) -> float:
    total = int(total or 0)
    return float(passed or 0) / total if total else 0.0


def load_json(path: Path) -> dict | None:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def latest(pattern: str) -> Path | None:
    """按 mtime 取最新匹配文件；没有返回 None。"""
    matches = [path for path in ROOT.glob(pattern) if path.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def _check(name: str, path: Path | None, actual: float | None, threshold: float) -> dict:
    if path is None or actual is None:
        return {
            "name": name,
            "path": str(path) if path else None,
            "actual": None,
            "threshold": threshold,
            "ok": False,
            "status": "missing",
        }
    return {
        "name": name,
        "path": str(path),
        "actual": round(float(actual), 6),
        "threshold": threshold,
        "ok": float(actual) >= float(threshold),
        "status": "pass" if float(actual) >= float(threshold) else "fail",
    }


def check_bfcl(path: Path | None, thresholds: dict) -> list[dict]:
    data = load_json(path) if path else None
    summary = (data or {}).get("summary") if isinstance(data, dict) else None
    if not isinstance(summary, dict):
        return [
            _check("BFCL exact", path, None, thresholds["bfcl_exact"]),
            _check("BFCL irrelevance", path, None, thresholds["bfcl_irrelevance"]),
        ]
    exact = summary.get("simple_exact_acc")
    if exact is None:
        exact = _ratio(summary.get("simple_exact"), summary.get("simple_total"))
    irrelevance = summary.get("irrelevance_no_call_rate")
    if irrelevance is None:
        irrelevance = _ratio(summary.get("irrelevance_no_call"), summary.get("irrelevance_total"))
    return [
        _check("BFCL exact", path, exact, thresholds["bfcl_exact"]),
        _check("BFCL irrelevance", path, irrelevance, thresholds["bfcl_irrelevance"]),
    ]


def check_public(path: Path | None, thresholds: dict) -> list[dict]:
    data = load_json(path) if path else None
    summary = (data or {}).get("summary") if isinstance(data, dict) else None
    if not isinstance(summary, dict):
        return [_check("MultiHop Hit@4", path, None, thresholds["rag_hit4"])]
    item = None
    for key, value in summary.items():
        if "multihop" in str(key).lower() and isinstance(value, dict):
            item = value
            break
    if item is None:
        return [_check("MultiHop Hit@4", path, None, thresholds["rag_hit4"])]
    return [_check("MultiHop Hit@4", path, item.get("hit_at_4"), thresholds["rag_hit4"])]


def check_agent(path: Path | None, thresholds: dict) -> list[dict]:
    data = load_json(path) if path else None
    summary = (data or {}).get("summary") if isinstance(data, dict) else None
    if not isinstance(summary, dict):
        return [_check("coding_demo pass", path, None, thresholds["agent_pass"])]
    actual = _ratio(summary.get("passed"), summary.get("total"))
    return [_check("coding_demo pass", path, actual, thresholds["agent_pass"])]


def check_structured(path: Path | None, thresholds: dict) -> list[dict]:
    data = load_json(path) if path else None
    summary = (data or {}).get("summary") if isinstance(data, dict) else None
    if not isinstance(summary, dict):
        return [
            _check("structured pass", path, None, thresholds["structured_pass"]),
            _check("structured schema", path, None, thresholds["structured_schema"]),
        ]
    passed = _ratio(summary.get("passed"), summary.get("total"))
    schema = _ratio(summary.get("schema_ok"), summary.get("total"))
    return [
        _check("structured pass", path, passed, thresholds["structured_pass"]),
        _check("structured schema", path, schema, thresholds["structured_schema"]),
    ]


def evaluate(
    bfcl_path: Path | None = DEFAULT_BFCL,
    public_path: Path | None = DEFAULT_PUBLIC,
    agent_path: Path | None = None,
    structured_path: Path | None = None,
    thresholds: dict | None = None,
) -> dict:
    thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    agent_path = agent_path or latest(DEFAULT_AGENT_GLOB)
    structured_path = structured_path or latest(DEFAULT_STRUCTURED_GLOB)
    checks = []
    checks += check_bfcl(bfcl_path, thresholds)
    checks += check_public(public_path, thresholds)
    checks += check_agent(agent_path, thresholds)
    checks += check_structured(structured_path, thresholds)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "ok": all(item["ok"] for item in checks),
        "checks": checks,
        "thresholds": thresholds,
    }


def print_report(result: dict) -> None:
    print(f"{'检查项':<22} {'实际':>10} {'阈值':>8}  状态")
    print("-" * 58)
    for item in result["checks"]:
        actual = "—" if item["actual"] is None else f"{item['actual']:.2%}"
        threshold = f"{item['threshold']:.2%}"
        print(f"{item['name']:<22} {actual:>10} {threshold:>8}  {item['status']}")
    print("-" * 58)
    print("GATE:", "PASS" if result["ok"] else "FAIL")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Agent 评测门禁")
    parser.add_argument("--bfcl", default=str(DEFAULT_BFCL))
    parser.add_argument("--public", default=str(DEFAULT_PUBLIC))
    parser.add_argument("--agent", help="coding_demo 报告；默认取最新")
    parser.add_argument("--structured", help="structured_demo 报告；默认取最新")
    parser.add_argument("--min-bfcl-exact", type=float, default=DEFAULT_THRESHOLDS["bfcl_exact"])
    parser.add_argument("--min-bfcl-irrelevance", type=float, default=DEFAULT_THRESHOLDS["bfcl_irrelevance"])
    parser.add_argument("--min-rag-hit4", type=float, default=DEFAULT_THRESHOLDS["rag_hit4"])
    parser.add_argument("--min-agent", type=float, default=DEFAULT_THRESHOLDS["agent_pass"])
    parser.add_argument("--min-structured", type=float, default=DEFAULT_THRESHOLDS["structured_pass"])
    parser.add_argument("--min-schema", type=float, default=DEFAULT_THRESHOLDS["structured_schema"])
    parser.add_argument("--json-out", help="可选：把 gate 结果写成 JSON")
    parser.add_argument("--require-all", action="store_true", help="缺失报告也视为失败")
    args = parser.parse_args(argv)

    def _path(value: str | None) -> Path | None:
        # 显式传入但缺失的路径也要保留，交给 check_* 标记为 missing；
        # 不能回退到“最新报告”，否则 --agent typo.json 会悄悄检查别的文件。
        return Path(value) if value else None

    thresholds = {
        "bfcl_exact": args.min_bfcl_exact,
        "bfcl_irrelevance": args.min_bfcl_irrelevance,
        "rag_hit4": args.min_rag_hit4,
        "agent_pass": args.min_agent,
        "structured_pass": args.min_structured,
        "structured_schema": args.min_schema,
    }
    result = evaluate(
        bfcl_path=_path(args.bfcl),
        public_path=_path(args.public),
        agent_path=_path(args.agent) if args.agent else None,
        structured_path=_path(args.structured) if args.structured else None,
        thresholds=thresholds,
    )
    if args.require_all:
        for item in result["checks"]:
            if item["status"] == "missing":
                item["ok"] = False
                item["status"] = "fail"
        result["ok"] = all(item["ok"] for item in result["checks"])

    print_report(result)
    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"details: {path}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
