# Agent 测试入口

框架与业务分离后，测试只依赖 `Scenario`：

- `scenarios/<场景>/cases.jsonl`：该场景的测试用例；
- `quality/agent_eval.py`：行为层 runner（FrameworkAgent）；
- `quality/judge.py`：可选 LLM-as-judge；
- `test_entry.py`：兼容入口；新入口是 `python -m quality.runner agent`。

## 用法

```bash
# 列出场景和用例
python test_entry.py --list

# 跑全部用例
python test_entry.py --all
python -m quality.runner agent

# 只跑一条
python test_entry.py --case agent-rag-001

# 交互式测试
python test_entry.py --interactive

# 加 LLM judge
python test_entry.py --all --judge

# 只跑前 3 条
python test_entry.py --limit 3
```

报告输出到 `outputs/agent/agent_test_<scenario>_<timestamp>.md/json`。

## Harness 能力演示

```bash
# 高风险工具审批：approve 或 reject
python tests/demos/hitl_demo.py --decision approve
python tests/demos/hitl_demo.py --decision reject

# 同一 thread_id 的多轮记忆
python tests/demos/memory_demo.py
```

- `hitl_demo.py` 会尝试触发 `HumanInTheLoopMiddleware` 并打印审批请求；
  模型也可能出于安全考虑直接拒绝调用高风险工具，此时不会进入审批，属于正常行为。
  reject 时工具不会执行（可观察 `[SIDE EFFECT]` 是否出现）。
- `memory_demo.py` 使用同一个 `thread_id` 验证多轮历史；默认 checkpointer 是 SQLite
  （`scenarios/robot_vacuum/config/agent.yml`），测试 runner 每次生成独立 thread_id，不会互相污染。

## 用例字段

```json
{
  "id": "agent-rag-001",
  "category": "rag",
  "question": "小户型适合哪些扫地机器人？",
  "expected_points": ["轻便", "小户型"],
  "expected_tools": ["rag_summarize"],
  "should_refuse": false,
  "notes": "选购指南"
}
```

判定：

- `expected_points`：回答中出现的比例 ≥ 50%；
- `expected_tools`：实际调用的工具必须包含全部期望工具；
- `should_refuse=true`：回答必须包含拒答标记；
- `--judge`：用 LLM 复核语义覆盖，替代关键词判定。

## 新增业务场景

1. 在 `scenarios/<name>/` 下实现 `build_scenario()`，返回 `Scenario`；
2. 在 `scenarios/registry.py` 注册；
3. 在场景目录放 `cases.jsonl`；
4. `python test_entry.py --scenario <name> --all`。

框架层 `agent/framework.py` 不需要改。
