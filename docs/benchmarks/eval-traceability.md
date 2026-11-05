# 评测结果到 trace 的链路

> 复核时间：2026-11-05 17:45–17:57
> 结论：三组主结果都能从报告回到原始 trace。workspace **15/15**；planner **24/24**（重跑后）；outcome **40/40**（36 个 trial + 4 个 router target，重跑后）。
> 本文只回答“这些数字从哪来、能不能查”，不重新解释指标定义。
> 注意：`outputs/` 下的报告和 trace 是本地生成物，不随仓库分发；清理后会断链。

## 1. 链路长什么样

```text
报告 md / JSON
  └─ results[].trace_id / trial_trace_ids
       └─ outputs/traces/trace_YYYYMMDD.jsonl
            └─ model_start / tool_start / tool_end / run_end
                 └─ 用例文件（cases.jsonl / outcome_cases.jsonl）
                      └─ 场景代码 / 数据路由
```

一条 trace 至少能回答三件事：跑了哪个场景、调了哪些工具、最后有没有正常结束。

## 2. Workspace 5/5：15 个 trial trace 全在

| 项 | 值 |
|---|---|
| 报告 | [agent_test_workspace_assistant_20261102_040642.md](../../outputs/agent/agent_test_workspace_assistant_20261102_040642.md#L4-L7) |
| 字段 | `results[].trial_trace_ids`（每条用例 3 个） |
| trace 文件 | [trace_20261102.jsonl](../../outputs/traces/trace_20261102.jsonl#L2414) |
| 复核结果 | 5 × 3 = **15/15** 都能在 trace 文件里找到 |

例子：`workspace-qa-001` 的第 3 个 trial 是 `run-448d2a21675e4e7fa05d38f9bda44483`：

```powershell
python -m core.observability.trace_report --trace-id run-448d2a21675e4e7fa05d38f9bda44483
```

事件序列是 `model_start → model_end → tool_start(search_notes) → tool_start(search_notes)
→ tool_end ×2 → model_start → tool_start(read_note) ×3 → run_end`，和用例期望的
“检索笔记 + 读笔记”对得上。

> 这份报告是 2026-11-02 的 3-trial 快照。当前 `cases.jsonl` 之后有过措辞调整，
> 引用数字时仍以这份报告为准；重跑会生成新报告。

## 3. Planning policy 12/12：旧报告没有 trace，已补并重跑

旧报告 [planner_eval_20261102_040054.json](../../outputs/experiments/planner_eval_20261102_040054.json)
只有 `correct / planned / latency / tokens`，**没有任何 trace_id**，所以旧结果无法回查执行轨迹。

这次重跑还先撞了一个 stale 问题：

```text
ImportError: cannot import name 'ROUTER_POLICY' from 'core.scenarios.router.scenario'
```

router 已经转成 spec-owned，旧的 `ROUTER_POLICY` 常量被删了；实验脚本没有跟着迁移。
修复方式是直接从路由表生成策略：

```python
from core.scenarios.router import routes as route_table

ROUTER_POLICY = route_table.build_policy(route_table.load_routes("router"))
```

同时给每条结果加了 `trace_id` 字段。新报告：

| 项 | 值 |
|---|---|
| 报告 | [planner_eval_20261105_174542.md](../../outputs/experiments/planner_eval_20261105_174542.md#L8-L11) |
| 字段 | `results[].trace_id`（12 条 prompt × baseline/policy） |
| trace 文件 | `outputs/traces/trace_20261105.jsonl` |
| 复核结果 | **24/24** 都能找到 |

新结果与旧口径一致：baseline **11/12**，policy **12/12**，policy 唯一一次 abstain
（英文 `Summarize the product brief...`）交回模型后仍路由正确；平均模型调用
1.92 → 1.08。

注意：这次 policy 平均时延 8.36s、baseline 9.89s，和旧报告的 19.9s / 9.6s 不同；
时延受目标场景负载/缓存影响，**不拿时延做“更快”的结论**。

## 4. Outcome 12/12：旧报告缺 workflow trace，修完重跑为 40/40

旧报告 [outcome_all_20261102_041146.md](../../outputs/outcome/outcome_all_20261102_041146.md)
是 12/12、13 个断言，但 12 条里只有 11 条有 `trace_id`；`research-outcome-workflow-001`
是空的，因为当时 `WorkflowRuntime` 没接 tracer。

更严重的是：router 转 spec 后，`deep_research` 的 `report` 节点其实已经坏了——
它把带换行的 `{answer}` 直接插进 JSON 字符串，`call_tool` 解析失败，报告没有落盘。
重跑这条用例时直接得到 `0/1`，才把问题暴露出来。

修复了两处：

1. `WorkflowRuntime.run()` 挂 `TraceCallbackHandler`，暴露 `last_trace_id`；
2. `call_tool` 的 JSON 参数模板增加转义回退：直接替换失败时，把占位符替换成
   `json.dumps(value)[1:-1]` 再解析。

新报告：

| 项 | 值 |
|---|---|
| 报告 | [outcome_all_20261105_175051.md](../../outputs/outcome/outcome_all_20261105_175051.md#L3-L8) |
| 字段 | `results.<scenario>[].trial_trace_ids`；router 另有 `checks[].trace_id` |
| trace 文件 | `outputs/traces/trace_20261105.jsonl` |
| 复核结果 | 36 个 trial trace + 4 个 router target = **40/40** |
| 结果 | 12/12 pass^k，13/13 断言 |

`research-outcome-workflow-001` 现在有 3 个 trial trace，且报告文件真的写到了
`data/runtime/research_assistant/reports/`。

## 5. 改了什么

| 文件 | 改动 |
|---|---|
| `core/experiments/planner_eval.py` | 从 `data/routes/router.json` 生成 policy；结果写 `trace_id` |
| `core/agent/workflow.py` | `WorkflowRuntime` 接入 tracer，暴露 `last_trace_id` |
| `core/quality/outcome_eval.py` | workflow 分支记录 trace；聚合结果写 `trial_trace_ids` |
| `core/scenarios/spec_nodes.py` | `render_json_template`：JSON 参数模板安全插值 |
| `tests/test_planning_policy.py` | 防止实验脚本再 import 已删除的 `ROUTER_POLICY` |
| `tests/test_spec_blocks.py` | 覆盖多行/带引号 answer 的 `call_tool` 插值 |

## 6. 复现

```powershell
python -m core.quality.runner agent --scenario workspace_assistant --trials 3
python -m core.experiments.planner_eval --trials 1
python -m core.quality.runner outcome --all --trials 3
python -m core.observability.trace_report --trace-id <trace_id>
```

测试：**399 passed**。

## 7. 还没补的链路缺口

- **trace 文件按天存放，没有保留策略**：`outputs/traces/trace_YYYYMMDD.jsonl`
  被清理后，旧报告里的 id 会失效。当前 10/28–11/05 的文件都在，但这不是保证。
- **报告没有记录 git commit**：现在只能回到文件级（哪份用例、哪段代码），不能从报告
  直接跳到当时的提交。要补的话，在报告 JSON 里加 `git_commit` / `cases_sha256`。
- **planner 只记录 router 外层 trace**：目标场景的 `target_trace_id` 在
  `route_to_*` 的返回值里，但没有写进 planner 报告；要看目标执行，得用 outcome 的
  `router_target` 断言或去 trace 文件里搜。
- **旧 outcome 报告只存了最后一次 trial 的 trace**：新代码会存 3 个，旧报告不会回填。
