# -*- coding: utf-8 -*-
"""把评测中的失败/部分通过案例归档为 failure set，供回归与面试复盘使用。

输入：
- evals/reports/eval_generation_judged.json（RAG 生成 + judge）
- tests/results/agent_test_robot_vacuum_*.json（最新 Agent 测试）
- evals/reports/eval_bfcl.json（BFCL 抽样）

输出：
- evals/failures/rag_failures.jsonl
- evals/failures/agent_failures.jsonl
- evals/failures/bfcl_failures.jsonl
- evals/failures/README.md
"""
import glob
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "evals" / "reports"
FAILURES = ROOT / "evals" / "failures"
TESTS = ROOT / "tests" / "results"
TAU2_RESULTS = Path(r"E:\CODE\benchmarks\tau2-bench\data\simulations\retail20_deepseek_judge\results.json")
TAU2_TASKS = Path(r"E:\CODE\benchmarks\tau2-bench\data\tau2\domains\retail\tasks.json")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def classify_rag(row):
    category = row.get("category", "")
    reason = str((row.get("judge") or {}).get("reason", ""))
    if category == "conflict" or "冲突" in reason or "不一致" in reason:
        return "conflict_handling"
    if "编造" in reason or "无依据" in reason or "幻觉" in reason:
        return "hallucination"
    if "拒答" in reason or "资料不足" in reason:
        return "refusal_error"
    if "遗漏" in reason or "未覆盖" in reason or "未提及" in reason:
        return "incomplete_answer"
    return "other"


def build_rag_failures():
    path = REPORTS / "eval_generation_judged.json"
    if not path.exists():
        return []
    data = load_json(path)
    rows = []
    for row in data.get("results", []):
        judge = row.get("judge") or {}
        if judge.get("verdict") not in {"fail", "partial"}:
            continue
        rows.append({
            "id": row["id"],
            "source": "rag",
            "category": row.get("category"),
            "question": row.get("question"),
            "expected_points": row.get("expected_points", []),
            "answer": row.get("answer"),
            "retrieved_sources": row.get("retrieved_sources", []),
            "judge_verdict": judge.get("verdict"),
            "judge_coverage": judge.get("coverage"),
            "judge_reason": judge.get("reason"),
            "failure_type": classify_rag(row),
        })
    return rows


def build_agent_failures():
    paths = sorted(glob.glob(str(TESTS / "agent_test_robot_vacuum_*.json")), key=lambda p: Path(p).stat().st_mtime)
    if not paths:
        return []
    data = load_json(Path(paths[-1]))
    rows = []
    for row in data.get("results", []):
        if row.get("passed"):
            continue
        failure_type = "missing_refusal" if row.get("should_refuse") else "incomplete_answer"
        rows.append({
            "id": row["id"],
            "source": "agent",
            "category": row.get("category"),
            "question": row.get("question"),
            "expected_points": row.get("expected_points", []),
            "answer": row.get("answer"),
            "tool_names": row.get("tool_names", []),
            "coverage": row.get("coverage"),
            "refused": row.get("refused"),
            "should_refuse": row.get("should_refuse"),
            "failure_type": failure_type,
        })
    return rows


def build_bfcl_failures():
    path = REPORTS / "eval_bfcl.json"
    if not path.exists():
        return []
    data = load_json(path)
    rows = []
    for row in data.get("results", []):
        if row.get("kind") == "simple" and not row.get("exact"):
            failure_type = "wrong_function" if not row.get("name_ok") else "argument_mismatch"
            rows.append({
                "id": row["id"], "source": "bfcl", "kind": "simple",
                "question": row.get("question"), "failure_type": failure_type,
                "expected_name": row.get("expected_name"),
                "expected_args": row.get("expected_args"),
                "actual": row.get("actual"),
            })
        elif row.get("kind") == "irrelevance" and not row.get("no_call"):
            rows.append({
                "id": row["id"], "source": "bfcl", "kind": "irrelevance",
                "question": row.get("question"), "failure_type": "unnecessary_tool_call",
                "expected": "no tool call", "actual": row.get("actual"),
            })
    return rows


def build_tau2_failures():
    if not TAU2_RESULTS.exists() or not TAU2_TASKS.exists():
        return []
    results = load_json(TAU2_RESULTS)
    tasks = {str(task.get("id")): task for task in load_json(TAU2_TASKS)}
    rows = []
    for sim in results.get("simulations", []):
        reward_info = sim.get("reward_info") or {}
        if reward_info.get("reward") == 1.0:
            continue
        task = tasks.get(str(sim.get("task_id")), {})
        instructions = ((task.get("user_scenario") or {}).get("instructions") or {})
        breakdown = reward_info.get("reward_breakdown") or {}
        failure_type = "db_state_mismatch" if breakdown.get("DB", 1.0) == 0.0 else "nl_assertion_missing"
        rows.append({
            "id": f"tau2-retail-{sim.get('task_id')}",
            "source": "tau2",
            "category": "retail",
            "question": instructions.get("reason_for_call"),
            "failure_type": failure_type,
            "reward": reward_info.get("reward"),
            "reward_breakdown": breakdown,
            "nl_assertions": (task.get("evaluation_criteria") or {}).get("nl_assertions") or [],
        })
    return rows


def main():
    FAILURES.mkdir(parents=True, exist_ok=True)
    rag = build_rag_failures()
    agent = build_agent_failures()
    bfcl = build_bfcl_failures()
    tau2 = build_tau2_failures()

    write_jsonl(FAILURES / "rag_failures.jsonl", rag)
    write_jsonl(FAILURES / "agent_failures.jsonl", agent)
    write_jsonl(FAILURES / "bfcl_failures.jsonl", bfcl)
    write_jsonl(FAILURES / "tau2_failures.jsonl", tau2)

    from collections import Counter
    rag_types = Counter(row["failure_type"] for row in rag)
    agent_types = Counter(row["failure_type"] for row in agent)
    bfcl_types = Counter(row["failure_type"] for row in bfcl)
    tau2_types = Counter(row["failure_type"] for row in tau2)

    summary = {
        "rag": {"total": len(rag), "types": dict(rag_types)},
        "agent": {"total": len(agent), "types": dict(agent_types)},
        "bfcl": {"total": len(bfcl), "types": dict(bfcl_types)},
        "tau2": {"total": len(tau2), "types": dict(tau2_types)},
    }
    (FAILURES / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    readme = f"""# Failure Set

从最新一轮评测中归档的失败/部分通过案例，用于回归测试和面试复盘。

## 内容

| 文件 | 数量 | 来源 | 主要失败类型 |
|:---|:---:|:---|:---|
| `rag_failures.jsonl` | {len(rag)} | RAG 42 条业务集 + Judge | {dict(rag_types)} |
| `agent_failures.jsonl` | {len(agent)} | Agent 13 条行为用例 | {dict(agent_types)} |
| `bfcl_failures.jsonl` | {len(bfcl)} | BFCL 200 条抽样 | {dict(bfcl_types)} |
| `tau2_failures.jsonl` | {len(tau2)} | τ²-bench retail 20 条抽样 | {dict(tau2_types)} |

## 字段

- RAG：`id / category / question / expected_points / answer / retrieved_sources / judge_verdict / judge_coverage / judge_reason / failure_type`
- Agent：`id / category / question / answer / tool_names / coverage / refused / should_refuse / failure_type`
- BFCL：`id / kind / question / failure_type / expected_* / actual`

## 使用方式

1. 每条失败案例都应该进入回归集，修复后重跑；
2. 不要只针对单条 case 调 Prompt，先归类失败类型；
3. 面试时优先讲"失败类型 + 根因 + 下一步"，而不是单个 badcase；
4. 重新生成：`python evals/scripts/build_failure_set.py`。

## 口径

这是自建/抽样评测的失败集，不是线上真实 badcase；样本量小，结论以方向为主。
"""
    (FAILURES / "README.md").write_text(readme, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
