# 项目边界与冻结（2026-11-05）

> 结论：**冻结当前能力范围**。之后只修 bug、补文档、改口径，不再加功能、不再扩评测边界。
> 需要扩边界时，先改这份文档并说明冻结例外，不在口头层面“顺手加”。

## 1. 当前在边界内

| 层 | 内容 | 证据 |
|---|---|---|
| 运行时 | `Scenario` 契约、中间件流水线、HITL、checkpoint、token 预算、trace | `core/agent/` |
| 场景 | 11 个 spec-owned 场景，6 个已发布 | `data/specs/*/entry.yml` |
| 低代码 | 画布 + 表单 + 多路 `branch`（cases/default），编译期条件边校验 | `core/scenarios/spec_nodes.py`、`spec.py` |
| RAG | domain/category 过滤、服装按语义取样、100问/故障排除 FAQ 按编号切块 | 835 chunks；`data/knowledge/` |
| 控制台 | 对话 / 构建 / 质量三产品；知识库、基准目录、其他基准分组 | `core/interfaces/console/` |
| 评测 | capability / behavior / outcome；pass^k；BFCL fixture 矩阵；selfbuilt fixture | `core/quality/` |
| 可追溯 | 报告 → trace_id → trace JSONL → 用例 → 代码 | `docs/benchmarks/eval-traceability.md` |

## 2. 冻结时的数字

- 测试：**408 passed**（冻结时；2026-11-06 数据集/资源重构后为 **453 passed**）
- selfbuilt：**26/26**（1-trial）
- 新场景 3-trial：`clothing_service` **6/6**、`retail_router` **5/5**
- workspace：**5/5**（3-trial，11/02 快照）
- planning policy：**12/12**（baseline 11/12，11/05）
- outcome：**12/12**（13/13 断言，11/05）
- BFCL fixture 矩阵：**32/40**；missing 变体 **2/10**
- catalog：**11 个来源 / 132 条**
- 知识库：**835 chunks**（FAQ 切块后）

## 3. 边界外（明确不做）

1. **非 BFCL 族的 task tool adapter**（P1-6）：需要按族接 `TaskToolAdapter` / 官方环境，属于扩边界；
2. **全量 300 条 benchmark 端到端执行**（P1-5）：目前只有 catalog 数据和部分能力层/外部 harness；
3. **新场景 3-trial 以上的稳定性结论**：现有 3-trial 是小样本，不做统计显著性声明；
4. **多 Agent handoff / 生产部署 / 多模态 / 真实用户流量**：未实现；
5. **官方 benchmark 榜单分数**：BFCL 是抽样 + 简化评分，τ² 测的是官方 harness；
6. **trace 长期保留策略**：本地按天 JSONL，没有轮转/归档。

## 4. 冻结后的变更规则

- 允许：修 bug、修文档数字、补测试、修失效链接；
- 不允许：新场景、新块类型、新评测族、新 UI 大改；
- 例外：必须在本文件新增“冻结例外”并写明原因、证据、回退方式；
- 全量真实模型评测只在“要报数字/确认回归”时跑，不用于日常调试。

## 5. 冻结例外

### 例外 1：`fallback_answer` 块（2026-11-06）

- **原因**：规则没命中 / 多领域都命中时，现有 spec 工作流只能拒答；需要一条"交回模型、由它判断信哪份材料"的路径，并且它要能在画布上加/换，用来演示"结构可编辑"。
- **破了哪条**：第 4 节"不允许新块类型"。
- **范围**：只加一个块（+ 5 条单测）；不改执行器、不加场景、不改 UI、不改 active spec。
- **证据**：[`tests/test_fallback_node.py`](../../tests/test_fallback_node.py) 5 passed；块契约测试（`test_scenario_spec` / `test_spec_ports` / `test_node_docs`）全绿。
- **回退**：删块 + 删测试；active spec 没动，回退成本为零。
- **未做**：没有真实模型评测，没有 fallback 率的数字；多库全查的成本没有测量。
- 设计见 [fallback-node](fallback-node.md)。

### 例外 2：数据集外置 + 资源目录 MCP（2026-11-06）

- **原因**：仓库不应携带公开 benchmark 抽样正文，也不应把作者机器的
  `E:\CODE\benchmarks` 写死；同时 agent 编辑需要统一的工具 / 工作流 / 场景 /
  块访问面，而不是按四个模块的内部结构猜。
- **破了哪条**：第 4 节“不允许新能力”；严格说新增了只读资源目录和本地 MCP server。
- **范围**：
  - 采样实现移到 `dataset_ops/`，旧路径保留 shim；
  - 公开样本 / 分层正文 / catalog 正文移到 `data/datasets/`（git 忽略），仓库只留
    provenance 与 `data/benchmarks/manifest.json` 引用；
  - 新增 `core/paths.py`、`core/resources/`、`core/mcp/resource_server.py`；
  - **不动评测大框架**（runner / scorer / report 结构不变），只维护接口。
- **证据**：`python -m pytest -q` **453 passed**；MCP stdio smoke 能列出 4 个工具并
  返回 52 tools / 10 workflows / 11 scenarios / 12 blocks；旧
  `python -m core.quality.stratified` 与 `python -m core.benchmarks.catalog --list` 仍可用。
- **回退**：删除 `core/resources/` 与 `resource_server.py` 即回到无资源目录；
  数据从 `data/datasets/` 移回旧路径即可；`dataset_ops` 可由 shim 反向依赖。
- **未做**：没有把评测框架重构成统一 `EvalCase/Scorer`；没有向量语义检索；
  没有资源写入 API；没有把用户本地 `retail_router` 改动纳入提交。
- 设计见 [core-modularity](core-modularity.md)、
  [resource-catalog](resource-catalog.md)、
  [eval-interface-freeze](eval-interface-freeze.md)。

## 6. 叙事材料

- [A · 项目演进](../narrative/A-project-evolution.md)
- [B · 优化案例](../narrative/B-optimization-cases.md)
- [C · 现场编辑剧本](../narrative/C-live-edit-script.md)
- [叙事索引](../narrative/README.md)
