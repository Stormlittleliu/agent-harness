# 范式 → 候选 spec：只编译，不采纳

> 对应 `core/scenarios/pattern_to_spec.py`（编译）与 `core/quality/shadow.py`
> （baseline/candidate 对比）。M2。

## 1. 流水线位置

```text
M1 mining.py         → patterns.json（candidate，只读）
M2 pattern_to_spec   → candidates/<pattern_id>.json（候选 spec，不覆盖 active）
M2 shadow            → shadow.json（两边都跑，只记录）
M3 A/B + UI          → 人工采纳 / 回退
```

M2 的关键约束：**候选不是 active**。`pattern_to_spec` 不写 `active.json`、
不产生 `vN.json`；采纳是 M3 的事。

## 2. 步骤怎么映射成块

`pattern_to_spec` 只认已注册块，映射顺序如下：

| 步骤 | 映射 | 说明 |
|---|---|---|
| 源 spec 的节点 id（如 `search`） | 复用该节点的 `fn` + `args` | 最可靠；保留原参数 |
| 已注册块名（如 `retrieve`） | 该块 + 默认参数 | 必填参数从工具白名单补 |
| `tool:search_notes` | `call_tool(tool=search_notes, args={"query":"{input}"}, save_to="tool_result")` | ReAct 轨迹里的工具 token |
| `model` / `llm` | `llm_answer` | ReAct 里的模型 token |
| `branch` | **拒绝** | 线性工作流表达不了条件边的两个目标 |
| 其他 | 报错 | 不猜 |

必填参数补不出来时直接失败，例如：

- `retrieve.tool`：从工具白名单取第一个；白名单为空就报错；
- `react_loop.tools`：取整个工具白名单；
- `constant.text` / `llm_text.prompt`：范式里没有业务文案，要求源 spec 提供，不自动编。

带 `fan_out` 的范式如果源 spec 没有 `scratch.queries` 的上游产出，会在端口校验
阶段被拒绝——这比运行到一半才发现更好。

## 3. 编译与落盘

```python
spec = pattern_to_spec(pattern, scenario="workspace_assistant",
                       source_spec=active_spec, tool_names={"search_notes"})
# 内部顺序：
# 1) 步骤解析 + 必填参数补齐
# 2) 线性边 START → ... → END
# 3) validate_spec（含端口数据流校验）
# 4) build_workflows 真编译一次
# 5) 写 data/specs/<scenario>/candidates/<pattern_id>.json
```

- 候选文件包含 `provenance`：pattern id、name、kind、scope、support、
  success_rate、lift、evidence run ids、created_at、status=candidate；
- `pattern_id` 会做文件名清洗，防止 `../` 路径穿越；
- 如果给了 `source_spec`，候选会复制它的工具、提示词、harness、policies，
  只替换 `workflows`；这样 shadow 比较的是“同一场景换流程”，不是换场景；
- 不给 `source_spec` 时生成最小 spec，工具清单来自 `tool_names`。

## 4. Shadow：两边都跑，只记录

`run_shadow(baseline, candidate, cases, runner=...)`：

1. `split_cases` 按 `sha1(seed:case_id)` 排序，标 `train` / `held_out`；
2. 每条 case 在 baseline 和 candidate 上各跑一次（同一个 runner）；
3. 记录 pass、工具名、回归、改进、train/held-out 通过率；
4. 写 `outputs/shadow/<shadow_id>/shadow.json`；
5. `decision` 永远是 `pending`，**不写 `data/specs`、不切换场景**。

默认 runner 用 `agent_eval.evaluate_case`；测试注入确定性的 runner，
所以 shadow 的单测不需要模型。真正的模型 A/B 由 M3 的页面/CLI 调起。

## 5. 命令

```powershell
# 先挖
python -m core.quality.mining --scenario workspace_assistant --min-support 3

# 再编译某条范式（不采纳）
python -m core.scenarios.pattern_to_spec `
  --patterns outputs/patterns/<mining_id>/patterns.json `
  --pattern-id pat-xxxxxxxxxx `
  --scenario workspace_assistant

# 只校验、不写盘
python -m core.scenarios.pattern_to_spec --patterns ... --dry-run
```

## 6. 边界

- 只编译线性范式；分支/子图在 M4；
- 不自动采纳，不自动改 active；
- 不补业务文案；必填参数缺失就失败；
- shadow 不是 A/B 门槛：它只提供证据，门槛（pass^k、outcome、成本、安全）
  在 M3 实现；
- 候选文件不会被 `spec_scenario_names` 当成场景（只看 `active.json`）。
