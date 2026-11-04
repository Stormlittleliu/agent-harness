# 当前进度与下一步队列

> 这是压缩上下文后的恢复入口。先读这一页，再按顺序做；不要重做已完成的导航 A。
> 最近更新：2026-11-04。仓库：`E:\CODE\ag_learn\others\my_agent_harness`（MIT）。

## 1. 已完成

| 提交 | 内容 |
|---|---|
| `7c3f7f4` | 控制台导航 A：产品级固定 segmented tab、构建页签统一、对话入口左栏、开场白 chip、header 点击死区修复 |
| `24aa5e6` | `docs/design/editor-ux.md`：编辑器工作台、撤销/缩放/脏状态/保存并验证 |
| `8cf8408` | `docs/design/workflow-mining.md`：评测轨迹 → 成功范式 → 工作流 |
| `9f69f83` | `docs/design/open-source-borrowing.md`：LangGraph/Langflow/Promptflow/Rivet/Inspect 对标 |
| `c6be957` | P0-1/P0-2：run/line/score/span 记录 + Scorer/Metric/Reducer + trace span |
| `03461a1` | P0-3：块 `PortSpec` 输入/输出契约 + `block_ports` 动态端口 + `validate_port_flow` 静态数据流校验 |

最近一次全量测试：**312 passed**。

### 已落地的质量地基

```text
outputs/runs/<run_id>/
  run.json        # 场景 / 用例数 / trials / summary / metrics
  lines.jsonl     # 一行一个 case × trial，line_id = run_id:index
  metrics.json    # 按 score.name 聚合 mean / pass_rate / pass^k
```

- `core/quality/records.py`：`RunStore / RunRecord / LineRecord / Span / Score`
- `core/quality/scorers.py`：behavior/judge/outcome → `Score`；pass^k / pass@k / mean / defect_rate
- `core/quality/trace_spans.py`：现有 trace JSONL → `Span`
- `core/quality/agent_eval.py`：`run()` 已按 trial 写入 run 目录，保留旧 JSON/Markdown 报告

### 已落地的端口契约（P0-3）

- `core/scenarios/spec_nodes.py`：`PortSpec` + `block_inputs` / `block_outputs` / `block_ports`
- 参数层（`ParamSpec`）与端口层（`PortSpec`）分离；`save_to` / `queries_from` /
  `field` / `query_key` / 模板占位符会解析成动态端口
- `core/scenarios/spec.py`：`validate_port_flow` 从 `input:text` 求不动点，
  报"必填输入缺失"与"类型不兼容"；**不改执行器**
- 所有 active spec 仍零错误；说明见 `docs/design/node-ports.md`

## 2. 下一步队列（按顺序）

### M1 · 序列/转移挖掘（只读）

- 新建 `core/quality/mining.py`，读 `outputs/runs/*/lines.jsonl` + spans。
- 先做两件：连续序列模式（PrefixSpan 或自写 Apriori）、`from_node → to_node`
  转移 n-gram；不做完整 gSpan。
- 过滤成功 run；按 `support × success_rate × lift / cost` 排序。
- 输出 `outputs/patterns/<run_id>/patterns.json` + 可读范式卡。
- 验收：用合成 trace + 真实 run 至少各跑通一次；**不自动采纳**。

### M2 · pattern_to_spec + shadow

- `core/scenarios/pattern_to_spec.py`：pattern → candidate spec；
  只允许已注册块，不覆盖 active，走 `validate_spec`/`build_workflows`。
- 生成到 `data/specs/<scenario>/candidates/` 或临时目录；记录 provenance。
- shadow：原 cases + held-out 各跑一遍，只记录，不切换。
- 验收：一个线性范式能编译成可运行 spec。

### M3 · A/B + UI

- 质量页新增「范式」视图：列表 / 证据 / 指标 / 试运行 / 采纳 / 拒绝。
- 采纳门槛：pass^k 不降、outcome 不降、成本在预算内、无安全回归。
- 采纳后保留 baseline，一键回退。
- 验收：采纳后 pass^k 不降，能回退。

### 编辑器 P0（可与 M1 并行）

- 三栏工作台：左块库 / 中画布 / 右检查器；底部状态栏。
- 撤销/重做、框选、Delete、缩放/平移、草稿按场景保存、错误点击定位。
- 详见 `docs/design/editor-ux.md`；先做 P0，不做多选/复制/保存并跑用例（P1）。

### 质量页 P1（导航 A 的剩余项）

- 质量页 8 个视图分组（跑一次 / 看资产 / 查记录），去掉横排 8 个 radio。
- 去掉重复 H4；构建库 9 行「打开」改轻量行式操作。
- 详见 `docs/design/console-ia.md`。

## 3. 不要做 / 边界

- 不复制 GPL（ComfyUI）或自定义许可（Dify/n8n）代码；只借机制，代码原创。
- 不自动采纳 pattern；必须 held-out + A/B + 人工确认。
- 画布只改拓扑和位置；参数/结构以 spec 为单一权威。
- 中间件顺序仍由 slot + 不变量保证，不做成可拖拽。
- 不做整平台替换（Langflow/Dify/Flowise）；它们只作为对标。

## 4. 常用命令

```powershell
conda activate langchain
$env:PYTHONIOENCODING="utf-8"
cd E:\CODE\ag_learn\others\my_agent_harness

python -m pytest -q
python -m core.quality.runner agent --scenario workspace_assistant --trials 3
python -m core.quality.runner outcome --scenario workspace_assistant --trials 3

git status -sb
git log --oneline -10
```

## 5. 恢复时怎么说

> 继续按 `docs/design/plan-status.md` 的顺序做，从 M1（序列/转移挖掘，只读）开始；
> 不要重做导航 A 和 P0-3，不要整平台替换，不要自动采纳 pattern。
