# 评测轨迹挖掘：从成功运行到可编辑工作流

> 一句话：评测不再只给一个分数，而是把“成功的跑法”记成轨迹，
> 从轨迹里挖出高频繁荣范式，编译成 spec 工作流，再用 held-out 评测决定
> 能不能采纳。它是“评测 → 经验 → 工作流”的闭环。

> **实现状态（M1 只读挖掘）**：`core/quality/records.py` 提供
> run/line/score/span + `RunStore`；`core/quality/scorers.py` 提供
> behavior/judge/outcome → Score 与 pass^k reducer；`core/quality/trace_spans.py`
> 把 trace JSONL 读成 span；`agent_eval.run()` 写 `outputs/runs/<run_id>/`。
> `core/quality/mining.py` 已实现序列/转移挖掘、门槛过滤、证据与范式卡，
> 产物在 `outputs/patterns/<mining_id>/`；**只产出 candidate，不自动采纳**。
> M2 已实现：`core/scenarios/pattern_to_spec.py` 把线性范式编译成
> `data/specs/<scenario>/candidates/` 候选 spec（不覆盖 active）；
> `core/quality/shadow.py` 让 baseline/candidate 各跑一遍并只记录。
> 采纳与 A/B 门槛（M3）尚未开始。

## 1. 为什么做这个

现在评测的产出是：

```text
case → pass/fail → 报告
```

它回答“这次成没成”，不回答“为什么成、下次怎么复用”。这个功能补的是：

```text
run trace → 成功模式 → candidate workflow → A/B → 采纳/回退
```

它和项目已有的三件事天然咬合：

- `spec-owned`：范式最终落成 spec，不是另一套代码；
- `outcome eval`：成功不只看文本，还看环境状态；
- `pass^k`：范式是否稳定，用多次 trial 验证，而不是一次运气。

## 2. 不做什么

- 不做“自动改生产工作流”：只生成 **candidate**，必须人工采纳。
- 不做“从一次成功就总结”：最小 support、held-out、A/B 三道门。
- 不引入 GPL 的流程挖掘库；先用简单、可解释的序列/转移 n-gram。
- 不把原始参数、用户输入、PII 直接写进 pattern；只存摘要和证据引用。

## 3. 数据模型

### 3.1 Trace

每次 run 一条 JSONL，事件按 step 排序：

```json
{
  "run_id": "run-...",
  "scenario": "workspace_assistant",
  "case_id": "workspace-qa-001",
  "trial": 1,
  "spec_version": "v3",
  "graph_hash": "sha256:...",
  "outcome": "pass",
  "scores": {"behavior": 1.0, "outcome": 1.0, "judge": 0.9},
  "events": [
    {"step": 1, "kind": "node", "name": "retrieve", "status": "ok",
     "args_digest": "a1b2", "args_summary": "query=...", "latency_ms": 120},
    {"step": 2, "kind": "tool", "name": "search_notes", "status": "ok",
     "from_node": "retrieve", "to_node": "answer"},
    {"step": 3, "kind": "branch", "name": "has_citation", "condition": "false",
     "from_node": "verify", "to_node": "rewrite"}
  ]
}
```

约定：

- `kind`：`node | tool | llm | branch | retry | interrupt | error`；
- `from_node` / `to_node`：执行到的图转移，用于图挖掘；
- `args_digest`：参数归一化后的 hash；`args_summary` 只放脱敏摘要；
- 原始 trace 仍由现有 `core/observability/tracer.py` 保存，pattern 只引用 `run_id`。

### 3.2 Pattern

```json
{
  "id": "pat-2026-11-05-001",
  "name": "先检索再引用校验",
  "scope": {"scenario": "workspace_assistant", "intent": "qa"},
  "kind": "sequence",
  "nodes": [
    {"block": "retrieve", "role": "retrieve"},
    {"block": "llm_answer", "role": "answer"},
    {"block": "require_citation", "role": "verify"}
  ],
  "edges": [["retrieve", "llm_answer"], ["llm_answer", "require_citation"]],
  "slots": ["query", "source_filter"],
  "support": 18,
  "success_rate": 0.94,
  "lift": 0.12,
  "evidence": ["run-...", "run-..."],
  "counterexamples": ["run-..."],
  "cost": {"avg_tokens": 3200, "avg_latency_ms": 1800},
  "source": "mined",
  "status": "candidate"
}
```

`status`：`candidate → validated → adopted / rejected`。
`source`：`mined | manual`，保证可追溯。

## 4. 流水线

```text
record → normalize → mine → summarize → compile → A/B → adopt
```

### 4.1 Record

- 在 `FrameworkAgent` / workflow runtime 的 tool/node 钩子上记录事件；
- 评测 runner 写入 `case_id`、`trial`、`outcome`、`scores`；
- 复用 `run_id` / `trace_id`，不新建第二套 ID；
- 产物：`outputs/traces/<scenario>/<run_id>.jsonl` + `outputs/traces/index.sqlite`。

### 4.2 Normalize

- 工具名、节点名做 canonical 化；
- 合并连续 retry，保留 `retry_count`；
- 删除纯噪声事件（心跳、空 observation）；
- 按 `scenario + intent` 分桶，避免跨任务硬比较；
- PII 脱敏；参数只保留 digest + 摘要。

### 4.3 Mine

先做两层，按投入产出排序：

1. **序列模式**：把 trace 压成 `(kind, name)` 序列，用 PrefixSpan/自写 Apriori 找
   support ≥ N 的连续子序列。适用于线性流程、工具序列。
2. **转移 n-gram**：把 `from_node → to_node` 作为 token，找高频转移和分支组合。
   适用于有分支的图，不需要完整 gSpan。
3. （后置）**子图挖掘**：只对节点数 ≤ 20 的图做 gSpan/近似子图；先不做。

排序分：

```text
score = support × success_rate × lift / cost_penalty
```

要求：`support ≥ 5`、`success_rate ≥ baseline`、`lift > 0`；低于门槛不展示。

### 4.3.1 当前实现（M1）

`core/quality/mining.py`：

- **归一**：spec 工作流的 trace 用真实节点名；ReAct 的 `model/tools` 这类通用
  节点名改用 `tool:<name>` / `model`，否则整条序列全是 `tools`。相邻重复 token 合并。
- **分桶**：按 `scenario × intent`（`line.metadata.category`）分桶，不同意图不硬比较。
- **序列**：只挖长度 ≥ 3 的连续子序列（两跳交给转移层，避免同一件事两种写法）。
- **转移**：把相邻节点对 `a → b` 当 pattern；若与序列重复则保留序列。
- **support** 只统计成功 trial；`success_rate` 的分母是该 pattern 在所有 trial 里的出现次数；
  `lift = success_rate - baseline`。反例就是出现过该 pattern 但失败的 trial。
- **成本惩罚**：`1 + avg_tokens/4000 + avg_latency_ms/2000`。
- **产物**：`outputs/patterns/<mining_id>/patterns.json` + `patterns.md`；
  `mining_id` 默认按时间生成，重复挖掘不会覆盖。
- **基线 100% 时**：没有路径能超过基线，结果为空，范式卡会明确说明“先跑出失败样本”，
  而不是硬凑一个 lift=0 的“范式”。

```powershell
python -m core.quality.mining --scenario workspace_assistant --min-support 3 --top 10
```

### 4.4 Summarize

每个 pattern 生成一张“范式卡”：

- 什么时候用（scope / intent / 触发条件）；
- 步骤与分支（可读的节点序列）；
- 证据（成功的 run / case，反例）；
- 指标（support、success rate、lift、成本、延迟）；
- 风险（是否只在某个 case 上成立、是否依赖特定工具）。

### 4.5 Compile

`pattern_to_spec(pattern, base_scenario)`：

- 只允许 `spec_nodes` 里已注册的块，不允许内联代码；
- 参数从 pattern 填，未定的参数暴露成 slot；
- 生成新的 `data/specs/<scenario>/vN.json` 或新的 workflow，**不覆盖 active**；
- 走 `validate_spec` + `build_workflows`，失败就停在 candidate；
- pattern id / run ids 写进 spec 的 `provenance` 字段（新增可选字段）。

### 4.5.1 当前实现（M2）

- `core/scenarios/pattern_to_spec.py`：
  - 步骤优先按源 spec 节点 id 复用 `fn`/`args`，其次按块名、`tool:<name>`、`model` 映射；
  - 只编译线性工作流，`branch` 明确拒绝；
  - 候选写到 `data/specs/<scenario>/candidates/<pattern_id>.json`，
    **不写 `active.json`、不产生 `vN.json`**；
  - 过 `validate_spec`（含端口）并真的 `build_workflows` 一次；
  - `ScenarioSpec.provenance` 记录 pattern id / scope / 指标 / evidence runs。
- `core/quality/shadow.py`：
  - 确定性划分 train / held_out；
  - baseline 与 candidate 各跑一遍，记录回归/改进/held-out 通过率；
  - 只写 `outputs/shadow/<shadow_id>/shadow.json`，`decision=pending`；
  - runner 可注入，测试不需要模型。
- 详细边界见 `docs/design/pattern-to-spec.md`。

### 4.6 A/B

- 原 cases + held-out cases，各跑 `--trials 3`；
- 比较 `pass^k`、outcome 断言、成本、延迟；
- 门槛：success rate 不下降、outcome 不下降、成本在预算内、无安全回归；
- 先 shadow（只记录不切换），再人工采纳；
- 采纳后保留 baseline，支持一键回退。

## 5. UI

质量页新增「范式」视图（P2）：

```text
范式列表：名称 / scope / support / success / lift / 状态
详情：步骤图（只读） · 证据 · 指标 · 反例
操作：试运行 · 编译成 spec 草稿 · 采纳 · 拒绝
```

构建页的「发布」页签显示 `source: mined` 和 provenance，避免“这版是哪来的”说不清。

## 6. 分阶段

| 阶段 | 内容 | 验收 |
|---|---|---|
| M0 | trace schema + recorder + index | 一次评测能落 JSONL，能按 run/case 查 |
| M1 | 序列/转移挖掘 + 范式卡（只读） | 3 个场景 × 20 cases × 3 trials 能出 Top 10，带证据 |
| M2 | `pattern_to_spec` + 校验 + shadow | 一个线性范式能编译成可运行 spec，不覆盖 active |
| M3 | A/B 门槛 + 采纳/回退 + UI | 采纳后 pass^k 不降，能回退 |
| M4 | 分支/子图模式、跨场景库、漂移 | 分支模式可解释，跨场景不串味 |

先做 M0–M1，不要一上来做图挖掘。

## 7. 风险

- **相关≠因果**：成功 run 里常见，不代表加上它就成功；必须 A/B。
- **过拟合**：pattern 可能只记住某个 case；用 held-out + 最小 support。
- **工具/场景漂移**：工具改名、模型升级会让 pattern 失效；加 `last_validated_at`。
- **成本**：频繁挖掘是大计算；先离线、按需、限制图规模。
- **隐私**：trace 里有用户输入；默认脱敏，pattern 不存原文。
- **误导面试**：不要说“自动优化工作流”，要说“从成功轨迹提炼候选范式，评测门槛把关”。

## 8. 和现有设计的关系

- 不破坏 `spec-owned → eject → code-owned`：pattern 只是生成 spec 的一种来源；
- 不破坏 `route.tab` / 单一权威：candidate 不是 active，采纳才写版本；
- 不替代评测：评测是裁判，挖掘只是提出假设；
- 这是面试里很好的差异化：**“评测不只打分，还能把成功经验沉淀成可编辑的工作流，并且用 held-out 证明不是过拟合。”**
