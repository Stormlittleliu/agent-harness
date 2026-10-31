# P0 追加结果：成本 / 结构化输出 / 门禁 / 触发率

> 生成时间：2026-10-31
> 目的：把 P0-1 ~ P0-4 的实现与证据集中到一页，作为面试口径和后续回归基线。
> 原则：所有数字都带口径；成本是按配置单价估算，不是账单；触发率是小样本行为实验。

## 1. P0-1 成本 / 时延报告

命令：

```bash
python -m core.observability.cost_report
```

数据：`outputs/traces/trace_*.jsonl`，3203 条 run（快照；含历史 BFCL / RAG / MCP / coding 实验）。

| 指标 | 数值 |
|:---|:---:|
| Run 数 | 3203 |
| 成功 / 失败 / 未知 | 3104 / 55 / 0 |
| 成功率 | 98.3% |
| 延迟 p50 / p95 | 2.50s / 8.54s |
| 完成 run p50 / p95 | 2.46s / 8.52s |
| 模型调用 / 工具调用 | 6,693 / 5,709 |
| Token（输入 / 输出 / 总计） | 19,552,650 / 1,069,015 / 20,621,665 |
| 平均 Token / run | 6,438.2 |
| 估算总成本 | ¥47.6358 |
| 平均成本 / run | ¥0.0149 |
| 每个成功 run 成本 | ¥0.0135 |

**口径**

- 成本按 `config/observability.yml` 的示例单价（输入 ¥2 / 输出 ¥8 每百万 token）估算；
  这是本地估算，不是 DeepSeek 账单。价格会随时间和峰谷变化。
- 报告同时输出 `outputs/cost_report.json`，可被控制台“💸 成本 / 时延”页读取。
- 成功率只统计 `run_end.status == completed`；旧 trace 没有 `run_end` 时标记为 `unknown`。

**面试一句话**

> 我把已有 trace 聚合成准确率—时延—成本三维报告：3203 次 run，p95 8.54s，平均 6438 token，
> 按示例单价估算单次约 ¥0.015；这让我能在改 prompt/检索时不只看准确率，也看代价。

## 2. P0-2 结构化输出

实现：

- `Scenario.response_format` 透传给 LangChain `create_agent(response_format=...)`；
- `core/scenarios/structured_demo/schema.py` 定义 `ReportSchema`：
  `summary / evidence / confidence / next_actions / risks`；
- schema 校验失败由 LangChain 的 response format strategy 重试；
- `core/quality/structured_eval.py` 直接读取 `state["structured_response"]`，不解析自然语言。

命令：

```bash
python -m core.quality.runner structured
```

结果：

| 指标 | 数值 |
|:---|:---:|
| 用例数 | 5 |
| 通过 | 5/5 |
| schema 合法 | 5/5 |
| 平均置信度 | 0.654 |
| 平均证据条数 | 3.0 |

用例覆盖：办公会议纪要、学习笔记、内容脚本、客服工单、跨语言产品说明。

**口径**

- 5 条是自建小样本，不是公开 benchmark；
- 它证明 schema 约束和评测链路可用，不证明开放域报告质量；
- `structured_eval` 是严格 schema 评测；控制台“测试用例”页走通用关键词评分，两者不要混用。

**面试一句话**

> 我用 `create_agent(response_format=ReportSchema)` 把报告生成约束成 Pydantic schema，
> 评测直接读 `structured_response` 而不是解析自然语言；5 条跨办公/学习/内容/客服/跨语言用例
> schema 合法 5/5，平均 3 条证据。它还不是开放域质量评测，但把“结构化输出”从 prompt 约定变成了契约。

## 3. P0-3 评测门禁 + 故障注入

命令：

```bash
python -m core.quality.gate
```

当前结果：

| 检查项 | 实际 | 阈值 | 状态 |
|:---|:---:|:---:|:---:|
| BFCL exact | 90.00% | 90.00% | pass |
| BFCL irrelevance | 79.00% | 75.00% | pass |
| MultiHop Hit@4 | 55.56% | 50.00% | pass |
| coding_demo pass | 100.00% | 100.00% | pass |
| structured pass | 100.00% | 80.00% | pass |
| structured schema | 100.00% | 100.00% | pass |

```text
GATE: PASS
```

故障注入（`tests/test_fault_injection.py`，5 条确定性测试）：

| 故障 | 断言 |
|:---|:---|
| 工具超时 | 返回 `status="error"` 的 ToolMessage，不拖垮 run |
| 权限拒绝 | handler 不被调用，返回可读拒绝信息 |
| 参数格式错误 | 返回“参数校验失败”并提示修正 |
| 空检索 | `rag_retrieve` 返回空 content / 空 artifact，不崩溃 |
| 空检索后的拒答 | `score_case` 正确判定 refusal |

**边界**

- 门禁是“读取报告 + 阈值断言”，不是自动重跑评测；CI 里应先跑评测，再跑 gate。
- 还没有接 GitHub Actions；没有 shadow / A/B / 灰度。
- 阈值是当前基线，不是行业标准。

**面试一句话**

> 我把评测从“跑完看报告”变成“可执行的门禁”：BFCL、MultiHop、coding、structured 四项按阈值断言，
> 任一回归 exit 1；另外补了超时、权限、参数错误、空检索、拒答 5 类故障注入。
> 它还不是生产级 Ship Gate，但已经能阻止明显回退。

## 4. P0-4 subagent / 任务工具触发率

命令：

```bash
python -m core.experiments.trigger_rate
```

同一组 10 条自然任务，对比两版 system prompt：

| 版本 | Run | subagent 触发 | 任务工具触发 | 任一触发 | 平均工具数 |
|:---|:---:|:---:|:---:|:---:|:---:|
| natural（不提 subagent/任务） | 10 | 0/10 (0%) | 0/10 (0%) | 0/10 | 3.7 |
| routed（显式提示可用） | 10 | 0/10 (0%) | 0/10 (0%) | 0/10 | 3.7 |

对照：显式点名用例 `coding-subagent-001` 通过，coding_demo 5/5。

**解释**

- 这些任务用 `glob / read_file / run_command` 就能完成，模型选择直接工具是合理的；
- “提示里写了 subagent”不等于模型会自发委派；它需要 planner / policy 判断任务复杂度；
- 任务图同理：没有强依赖或多步骤信号时，模型不会先建 DAG；
- 这是一个负结果，但很有价值：它把“机制可用”和“行为可靠”分开了。

**面试一句话**

> 我做了触发率实验：10 条自然任务，natural 和 routed 两版 prompt 下 subagent/任务工具都是 0/10；
> 但显式点名用例能通过。说明机制没问题，缺的是 planner/routing，不是再写一个 subagent。
> 我不会把它说成“Agent 会自动多 Agent 协作”。

## 5. 对 JD 的影响

| JD 要求 | 之前 | 现在 |
|:---|:---:|:---:|
| 结构化输出 | 🟡 只有工具参数 schema | ✅ `response_format` + Pydantic + 5/5 |
| 时延 / 成本 | 🟡 trace 有数据，无报告 | ✅ 成本/时延报告 + 控制台页 |
| 准确性 / 稳定性 | ✅/🟡 有评测，无门禁 | ✅/🟡 gate + 故障注入，未接 CI |
| 多 Agent / 任务规划 | 🟡 单层 subagent | 🟡 机制有，触发率 0/10；缺 planner |
| 多模态 / 端侧 | ❌ | ❌ 仍是明确缺口 |

## 6. 复现命令

```bash
# 成本 / 时延
python -m core.observability.cost_report

# 结构化输出（5 条，会调用模型）
python -m core.quality.runner structured

# 评测门禁（只读报告）
python -m core.quality.gate --json-out outputs/gate_report.json

# 触发率实验（20 次 Agent run，会调用模型）
python -m core.experiments.trigger_rate

# 全部确定性测试
python -m pytest
```
