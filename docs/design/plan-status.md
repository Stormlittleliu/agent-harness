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
| `f8b2dfe` | M1：轨迹序列/转移挖掘 + 范式卡（只读，不自动采纳） |
| `dbdd613` | M2：线性范式 → `candidates/` 候选 spec + shadow 记录（不覆盖 active） |
| `62729f8` | M3：采纳门槛（pass^k/outcome/成本/安全）+ 版本回退 + 质量页「范式」视图 |
| `d22a365` | 编辑器 P0：三栏工作台、撤销/重做、按场景草稿、画布缩放/平移/Delete |
| `36de9f6` | 质量页 P1 收尾：去重复 H4、构建库「打开 →」改行内文字动作 |
| `9c511cb` | 编辑器交互：多选/框选、复制粘贴快捷键、画布可调尺寸、修复 START/END 回弹 |
| `c59a116` | 编辑器：Ctrl+X 剪切后粘贴恢复节点参数 |
| `4f0524a` | 编辑器：单击即刷新检查器、Ctrl+Z 保持视角、Alt 框选与多选持久化 |

最近一次全量测试：**381 passed**。

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

### 已落地的轨迹挖掘（M1）

- `core/quality/mining.py`：读 `outputs/runs/*/lines.jsonl` + spans
- 序列只挖长度 ≥ 3 的连续子序列；两跳交给转移层；按 `scenario × intent` 分桶
- ReAct 的 `model/tools` 归一成 `model` / `tool:<name>`；相邻重复 token 合并
- `support` 只算成功 trial，`success_rate` 分母是全部出现，`lift = success_rate - baseline`
- 产物 `outputs/patterns/<mining_id>/patterns.json` + `patterns.md`；
  **只产出 candidate，不自动采纳**
- 已用 2 个真实 run（6 条 trial）+ 合成 run 跑通；基线 100% 时明确输出"没有可挖范式"
- 说明见 `docs/design/workflow-mining.md` 的 4.3.1

### 已落地的候选编译与 shadow（M2）

- `core/scenarios/pattern_to_spec.py`：步骤按源 spec 节点 / 块名 / `tool:` / `model`
  解析；只编译线性范式，`branch` 明确拒绝
- 候选写 `data/specs/<scenario>/candidates/<pattern_id>.json`，
  **不写 `active.json`、不产生 `vN.json`**
- 必填参数补不出来就失败；候选必须过 `validate_spec` + `build_workflows`
- `ScenarioSpec.provenance` 记录 pattern id / scope / 指标 / evidence runs
- `core/quality/shadow.py`：确定性 train/held-out，baseline/candidate 各跑一遍，
  只写 `outputs/shadow/<shadow_id>/shadow.json`，`decision=pending`
- 说明见 `docs/design/pattern-to-spec.md`

### 已落地的采纳与回退（M3）

- `core/quality/adoption.py`：五道门槛（pass^k / outcome / token / 延迟 / 安全回归）
- 采纳写 `vN+1` 并切 active，baseline 版本保留；回退只改 `active.json` 指针
- 记录落 `outputs/adoptions/<scenario>/`，冲突时能回答"凭什么采纳"
- 质量页改为「跑一次 / 看资产 / 查记录」分组，新增「范式」视图：
  编译 / 试运行 shadow / 采纳 / 回退 / 拒绝
- 没有 shadow 或门槛不过时「采纳」不可点；页面不会自动跑模型
- 说明见 `docs/design/adoption.md`

### 已落地的编辑器 P0

- 三栏工作台：左工作流 + 块库 / 中画布或表单 / 右检查器 / 底部状态栏
- 50 步撤销/重做（结构、边、参数、画布拓扑）；撤销后换 widget 代次
- 草稿按场景存 session_state；未保存写 `data/runtime/spec_drafts/<name>.json`；
  切场景再切回不丢，状态栏有 `● 未保存`
- 画布：去掉 x=920 限制、滚轮缩放、空白平移、100%/+/-/适配、Delete、方向键微调
- 错误项「定位」选中对应节点
- 框选/多选/复制粘贴已在 P1 补齐；位置变更不进撤销栈；说明见 `docs/design/editor-ux.md`

### 已落地的编辑器 P1（多选与快捷键）

- Shift/Alt+点、Shift/Alt+拖空白框选；多选整体拖动、Delete、方向键微调
- 单击节点即刷新右侧检查器（不再需要先拖动）
- `Ctrl+C/X/V/D` 复制 / 剪切 / 粘贴 / 副本；参数按 `copy_of` 或 session 剪贴板恢复
- `Ctrl+Z/Y` 走 Python 撤销/重做栈；画布 key 稳定 + localStorage 视角，撤销不拉回视角
- 节点 184×64；画布右下角拖拽调高；状态栏「宽屏 / 还原宽度」
- START/END 位置不再被夹回画布内（修复拖拽回弹）
- 仍待做：连线端点重连、保存前 diff、保存并跑一条 case

### 已落地的质量页 P1

- 视图分组（跑一次 / 看资产 / 查记录）+ 「范式」视图
- 去掉「质量」+视图标题两个重复 H4
- 构建库「打开 →」改为透明行内文字动作，不再是一排按钮盒子
- 说明见 `docs/design/console-ia.md`

## 2. 下一步队列（按顺序）

### 编辑器 P1 剩余

- 连线端点重连（拖端点改目标，不必删了重画）。
- 保存前 diff；保存并跑一条 case（状态栏显示 pass/fail）。
- 详见 `docs/design/editor-ux.md` P1。

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

> 继续按 `docs/design/plan-status.md` 的顺序做，从编辑器 P1 开始；
> 不要重做导航 A、P0-3、M1/M2/M3、编辑器 P0，不要整平台替换，不要自动采纳 pattern。
