# 开源对标：代码分层、思想与可借鉴清单

> 对象：LangGraph、Langflow、Promptflow、Rivet、Inspect AI。
> 方法：浅克隆后只读分析，重点看“分层 / 核心抽象 / 执行与评测 / 契约 / 可迁移性”，
> 不比较 star，不推荐整平台替换。许可证以仓库当前 LICENSE 为准。

## 0. 一句话结论

这五个项目分别代表五种正确的分层方式：

- **LangGraph**：把“状态更新”变成 channel + superstep + checkpoint；
- **Langflow**：把“组件契约”投影成画布表单，把图当数据；
- **Promptflow**：把“一次运行”变成 run + line + variant + lineage；
- **Rivet**：把“图即程序”做成 NodeGraph + 类型化端口 + 解释器；
- **Inspect AI**：把“评测”拆成 Task / Solver / Scorer / Metric / Reducer + 样本日志。

用户项目最该补的不是画布，而是 **run/trace 记录**、**Scorer/Metric/Reducer 分层**、
**节点输入输出契约**。这三块补上，评测轨迹挖掘才有干净的数据底座。

## 1. 分层对照

| 项目 | 定位 | 代码分层 | 核心思想 | 许可 |
|---|---|---|---|---|
| **LangGraph** | 有状态图运行时 | `graph/` 声明层 · `pregel/` 引擎 · `channels/` 状态单元 · `checkpoint*` 持久化 | 状态是 channel，执行是 superstep，恢复靠 checkpoint | MIT |
| **Langflow** | 可视化 Agent 搭建 | `lfx/graph/` 图引擎 · `lfx/inputs/` 组件契约 · `api/build.py` 构建 API · 前端 flowStore | 画布 JSON 即数据，组件契约投影成表单 | MIT |
| **Promptflow** | 流程 + 批量评测 | `contracts/` 契约 · `executor/` DAG · `_core/` run 状态 · `_sdk/` run 管理 · `evals/` 评测 | run 是一等对象，line/node 双层记录，variant 可对比 | MIT |
| **Rivet** | 可视 AI 编程 | `core/model` 数据+解释器 · `core/model/nodes` 节点 · `app` 编辑器 · `node` 远程执行 | 图=数据，节点=契约，编辑器只是消费者 | MIT |
| **Inspect AI** | Agent 评测框架 | `dataset` · `_eval/task` · `solver` · `scorer` · `agent` · `log` | Task=数据集+Solver+Scorer；样本日志可回放 | MIT |

## 2. 最值得借的五件事（按优先级）

### P0-1 运行记录：run / line / sample / score 四层 ID

**来源**：Promptflow + Inspect AI。

- Promptflow：`run_id:index` 作为 `line_run_id`，node run 带
  `parent_run_id/root_run_id`，span 带 `batch_run_id+line_number`；
  元数据进 sqlite，产物进 run 目录（`snapshot/`、`outputs.jsonl`、`metrics.json`、
  `node_artifacts/`）。
- Inspect：`Sample` 是输入规格，`EvalSample` 是运行结果（messages/output/scores/
  events/usage/limits/error_retries），append-only 事件流。

**借到用户项目**：

```text
run_id（一次评测）
 └─ case_id（一条用例）
     └─ trial（第 k 次）
         └─ node/tool span（轨迹）
             └─ score（行为 / outcome / judge）
```

现有 `core/observability/tracer.py` 只有 `trace_id/thread_id/scenario`，缺
`case_id/trial/outcome/scores/node transition`。补上这四层，才能做轨迹挖掘。

### P0-2 评测分层：Scorer / Metric / Reducer 三分

**来源**：Inspect AI。

- `Scorer` 只对单样本产 `Score(value, answer, explanation, metadata)`；
- `Metric` 对 `list[SampleScore]` 聚合；
- `Reducer` 跨 trial 聚合；`pass^k = at_least(k, value=1.0)`，`pass@k = pass_at(k)`。

**借到用户项目**：

- 行为评测、outcome 断言、LLM judge 都产出同一种 `Score`，不再各写一套；
- `pass^k` 用 reducer 表达，不硬编码；
- 换 judge / 加断言可以 **rescore 旧日志**，不必重跑 agent。

这正好补 `core/quality/` 里 behavior/outcome/judge 三套口径不统一的问题。

### P0-3 节点契约：typed ports + DataValue + 参数 schema

**来源**：Rivet + Langflow。

- Rivet：`NodeGraph={nodes,connections}`；边只有 4 个 id；端口由
  `getInputDefinitions/getOutputDefinitions` 按需计算；`DataValue` 是
  `{type,value}` tagged union，支持 `string[]` / `fn<string>`；`visualData` 与
  语义数据分离。
- Langflow：组件类声明 `inputs=[...]`/`outputs=[...]`，`to_frontend_node()` 投影成
  画布节点；前端只按 `templateData.type` 渲染控件。

**借到用户项目**：

- 给 `spec_nodes` 的块加 `inputs`/`outputs`（名字、类型、必填、默认值），
  不只是 `ParamSpec`；
- 边校验从“节点存在”升级为“端口类型兼容”；`types_compatible` 独立纯函数；
- 画布只存 `id/type/x/y + 四元组边`，参数和端口定义留在 spec；
- 表单由 schema 生成，Python 仍是唯一校验权威。

### P1-1 图 spec：解析 / 引用校验分离 + position-only diff

**来源**：Langflow。

- `flow_builder/spec.py`：`parse_flow_spec` 只解析紧凑文本
  （`nodes/edges/config`），`validate_spec_references` 专门报“未知节点 + 可用候选”；
- `flow-diff.ts`：`diffGraphs` 产出 added/removed/modified，`isPositionOnly` 排除
  纯拖动；`applySelectedChanges` 选择性应用。

**借到用户项目**：

- 给编码 agent 一个 **text-first spec**，比让它直接改 JSON 更稳；
- 拖动只写 layout，不产生 spec 版本；版本 diff 只显示语义变化；
- 解析和引用校验分开，错误可修复（列出可用块/端口）。

### P1-2 运行对比：variant + lineage + resume

**来源**：Promptflow。

- `NodeVariant` 是一等公民，`overwrite_variant` 在临时目录重写 DAG，run 记录
  variant id；
- `evaluate()` 的 evaluator 也是 run，`run=target_run` 形成 lineage；
- `resume_from_run_storage` 复用成功 line，只重跑失败行。

**借到用户项目**：

- 「范式 A/B」直接用 run + variant 表达，不用另写对比脚本；
- 长评测中断后只重跑失败 case；
- 质量页从“读报告”升级为“读 run 目录 + 指标文件”。

### P2 运行时：channel / superstep / checkpoint / interrupt / Send

**来源**：LangGraph。

- `channels/base.py` 的 `update/get/checkpoint/from_checkpoint/consume`；
- `_algo.py` 的 `apply_writes` + 每任务写缓冲 + `writes_sort_key`；
- `Checkpoint` 三元组 + `put_writes` 先于快照；
- `interrupt()`/`Command(resume=)`；`Send` 做 fan-out。

**借到用户项目**：

- 中间件写状态改为显式 channel + reducer，失败不半写；
- 并行子 agent 写各自 deque，superstep 末统一提交；
- HITL 用 `interrupt`，恢复从 checkpoint 开始；
- fan-out 用 `Send`，但**不要**用它并行 N 个评测 case（一个 task 抛错会带走整步）。

## 3. 明确不要借

| 来源 | 不要借 | 原因 |
|---|---|---|
| LangGraph | `checkpoint_ns` 字符串编码、`configurable` 里的 30 个 `__pregel_*`、DeltaChannel/durability/streammux | 历史兼容/服务级复杂度；trace id 不可读，绑死 runtime |
| Langflow | catalog policy/可信代码哈希、`NodeData` 混视图字段、`custom_component/update` 模板回写、job queue/SSE 心跳 | 会让“策略/画布参数”变成第二权威；重型运行时与 spec 编译器无关 |
| Promptflow | Azure/PFS 常驻服务、ThreadLocalSingleton + 进程池、prompty DSL / tool_meta_generator / experiment orchestrator | 平台耦合、Windows 不稳定、与 LangGraph 定义重复 |
| Rivet | TS 类型体操、84 个内置节点、WS 远程协议、运行期不校验类型、`$if`/loopController 隐式控制流、v4 YAML hack | Python 用 Literal + 运行时表即可；隐式控制流难测 |
| Inspect | `TaskState` 可变全局 + contextvar、registry 装饰器重放、`.eval` zip/condense/View/control channel、Plan/epochs | 与 LangGraph 状态双事实源；运维面过重 |

## 4. 映射到用户项目

| 用户层 | 现状 | 借什么 | 来源 | 优先级 |
|---|---|---|---|---|
| `core/observability/tracer.py` | trace 只有 model/tool + trace_id | run/case/trial/span/score 四层 + append-only 事件 | Promptflow + Inspect | P0 |
| `core/quality/` | behavior/outcome/judge 三套口径 | Scorer/Metric/Reducer + rescore | Inspect | P0 |
| `core/scenarios/spec_nodes.py` | `ParamSpec`，无端口 | typed inputs/outputs + DataValue + 类型兼容 | Rivet + Langflow | P0 |
| `core/quality/runner.py` | 报告驱动 | run + line + variant + lineage + resume | Promptflow | P1 |
| `core/scenarios/spec_edit.py` | JSON 编辑 + 整图校验 | text spec 解析/引用校验分离 + position-only diff | Langflow | P1 |
| `core/agent/pipeline.py` | 隐式写 ctx | channel/reducer + superstep commit | LangGraph | P2 |
| `core/interfaces/dashboard/canvas/` | 自写 SVG | 端口按需计算 + 事件总线 + 声明式 EditorDefinition | Rivet + Langflow | P2 |

## 5. 和“评测轨迹挖掘”的关系

`docs/design/workflow-mining.md` 的第一步就是 M0：**trace schema + run record**。
没有 P0-1/P0-2，挖掘会变成：

- 没有 `case_id/trial/outcome` → 无法区分“成功”与“碰巧”；
- 没有统一 `Score` → 无法比较行为/outcome/judge；
- 没有稳定 `run/line/node` ID → 无法把 pattern 关联回证据。

所以顺序应该是：

```text
P0-1 trace/run schema
  → P0-2 scorer/metric/reducer
    → P0-3 typed ports（pattern 需要可组合的节点）
      → M0/M1 挖掘
        → M2 pattern_to_spec
          → M3 A/B 采纳
```

## 6. 建议的最小落地

不要一次抄五个项目。先做三件小事：

1. **`core/quality/records.py`**：定义 `RunRecord/LineRecord/NodeSpan/Score`，
   落 `outputs/runs/<run_id>/`；现有 tracer 只追加字段，不改调用方。
2. **`core/quality/scorers.py`**：把 behavior/outcome/judge 包成统一 `Score`；
   `pass^k` 写成 reducer；页面只读 `metrics.json`。
3. **`core/scenarios/node_ports.py`**：给块加 `inputs/outputs` 元数据，
   先只做校验和表单提示，不改执行器。

这三件加起来是“可测试的地基”，也是后续编辑器和轨迹挖掘的共同前置。

## 7. 关键参考（本地路径）

- LangGraph：`libs/langgraph/langgraph/pregel/_algo.py`（apply_writes / prepare_next_tasks）、
  `pregel/_loop.py`（tick/checkpoint/interrupt）、`channels/base.py`、`types.py`。
- Langflow：`src/lfx/src/lfx/graph/flow_builder/spec.py`、
  `graph/flow_builder/layout.py`、`graph/edge/base.py`、`graph/flow_builder/connect.py`。
- Promptflow：`src/promptflow-core/promptflow/contracts/flow.py`、
  `executor/_dag_manager.py`、`_core/run_tracker.py`、
  `src/promptflow-devkit/promptflow/batch/_batch_engine.py`。
- Rivet：`packages/core/src/model/NodeGraph.ts`、`NodeBase.ts`、`DataValue.ts`、
  `GraphProcessor.ts`、`EditorDefinition.ts`。
- Inspect：`src/inspect_ai/_eval/task/task.py`、`solver/_solver.py`、
  `scorer/_scorer.py`、`scorer/_reducer/reducer.py`、`log/_log.py`。
