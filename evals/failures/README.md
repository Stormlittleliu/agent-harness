# Failure Set

从最新一轮评测中归档的失败/部分通过案例，用于回归测试和面试复盘。

## 内容

| 文件 | 数量 | 来源 | 主要失败类型 |
|:---|:---:|:---|:---|
| `rag_failures.jsonl` | 4 | RAG 42 条业务集 + Judge | {'conflict_handling': 4} |
| `agent_failures.jsonl` | 2 | Agent 13 条行为用例 | {'incomplete_answer': 1, 'missing_refusal': 1} |
| `bfcl_failures.jsonl` | 31 | BFCL 200 条抽样 | {'argument_mismatch': 11, 'unnecessary_tool_call': 20} |
| `tau2_failures.jsonl` | 2 | τ²-bench retail 20 条抽样 | {'nl_assertion_missing': 1, 'db_state_mismatch': 1} |

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
