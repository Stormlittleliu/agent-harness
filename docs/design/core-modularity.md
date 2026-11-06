# Core 模块化审计（2026-11-06）

> 结论先行：**这轮只做“有外部消费者 / 有两个以上变更原因”的拆分，不按行数拆。**
> 已经落地：路径层、数据集采样外置、资源目录层。`spec_nodes`、`editor` 等大文件
> 继续保留，原因是它们各自只有一个变更原因，拆开只会增加 import 跳转。

## 1. 审计口径

不是“文件超过 500 行就拆”，而是看三件事：

1. 是否服务两个以上互不相关的变更原因；
2. 是否已有第二个消费者（CLI / MCP / 评测 / UI）需要绕过原本的私有逻辑；
3. 拆分后能否用接口测试锁住行为，而不是只移动代码。

不满足的，记录为“暂不拆”，避免为了结构图好看引入循环依赖。

## 2. 当前 core 分层

```text
core/
├── agent/          # Harness 契约、ReAct 运行时、中间件编排、subagent
├── tools/          # 业务工具 + RAG 能力（工具实现）
├── runtime/        # 工作区、任务图、命令执行
├── scenarios/      # 场景、spec、块库、归属、发布入口
├── resources/      # 新增：工具/工作流/场景/块的统一只读资源目录
├── quality/        # 评测框架与指标（本轮只维护接口）
├── benchmarks/     # 公开 benchmark 适配器与 runner（采样已移出）
├── mcp/            # MCP client + Fetch server + 本地资源 server
├── observability/  # trace、预算、成本报告
├── interfaces/     # CLI / Streamlit 三个产品
├── prompts/        # 提示词分块
├── experiments/    # 优化循环 / 实验
├── llm/ utils/     # 模型工厂、路径与配置
└── paths.py        # 新增：所有数据/运行时/数据集根的唯一定义
```

依赖方向仍然保持：

```text
interfaces → scenarios / quality / resources
scenarios  → agent.contracts / tools / prompts
agent      → contracts（不 import 具体场景）
resources  → 只读适配 scenarios / tools / specs（不反向被依赖）
```

## 3. 已落地拆分

### 3.1 路径层 `core/paths.py`

**问题**：`data/...` 在 20+ 个模块里重复拼路径；benchmark 源默认写死
`E:\CODE\benchmarks`，换机器就不可移植。

**处理**：所有根目录集中到 `core/paths.py`，支持：

- `AH_DATA_ROOT`：项目数据根；
- `AH_RUNTIME_ROOT` / `AH_SPEC_ROOT`：可写运行时 / spec 根；
- `AH_DATASET_ROOT`：外置数据集根；
- `AH_BENCHMARK_ROOT`：公开 benchmark 原始数据根，无默认绝对路径。

`core.utils.path_tool.get_abs_path("data/...")` 也改为委托 `DATA_ROOT`，
所以老调用点不需要一次性重写，但新代码应直接用 `core.paths`。

### 3.2 数据集采样 `dataset_ops/`

**问题**：`core/quality/stratified.py`（约 785 行）和
`core/benchmarks/sampling.py` 是“数据集生产工具”，不是 Harness 运行时；
它们依赖 benchmark 原始目录、会写大文件，和评测打分不是一类东西。

**处理**：实现移到顶层 `dataset_ops/`；`core.quality.stratified` 与
`core.benchmarks.sampling` 只保留薄 shim，保证旧 CLI 与测试接口不变。
这样 core 只保留“读数据集 / 跑评测”的引用面，采样器可以独立替换。

### 3.3 资源目录 `core/resources/`

**问题**：工具、场景、工作流、块分散在 `pools` / `library` / `spec` /
`spec_nodes` 四套结构里，agent 要编辑时得知道每个模块的内部形状。

**处理**：新增统一 `ResourceDescriptor` 与 URI
（`ah://tool/...`、`ah://workflow/<scenario>/<workflow>`、
`ah://scenario/...`、`ah://block/...`），由 providers 适配现有资源，
再由本地 MCP server 暴露 `resource_list/get/search/kinds`。资源目录只读，
不改变原资源的运行语义。

## 4. 暂不拆分（及原因）

| 模块 | 行数级别 | 为什么不这轮拆 |
|:---|:---:|:---|
| `core/scenarios/spec_nodes.py` | ~1k | 参数契约、端口契约、块实现、注册表共享同一组装饰器和 state 约定；拆出去只会制造 4 个互相 import 的文件。等出现第二个块实现来源时再拆。 |
| `core/interfaces/dashboard/editor.py` | ~1k | 画布/表单/草稿/发布都在一个 Streamlit 页面生命周期里；拆分需要先抽 UI 状态机，属于 UX 重构，不是本轮数据/资源重构。 |
| `core/scenarios/library.py` | ~330 | 静态元数据 + spec 发现 + UI 汇总看似三件事，但消费者只有 UI；资源目录上线后，静态表可以逐步变成 provider，届时再拆。 |
| `core/quality/*` | — | 用户明确“评测先不动大框架，只维护接口”；本轮只保证 CLI、数据集解析、报告路径不被数据外置破坏。 |
| `core/interfaces/dashboard/optimization.py` / `history.py` | ~800 | 各自是单页聚合视图，拆成组件会引入跨页状态；没有外部复用者。 |

## 5. 后续触发条件

满足任一条件再拆，不提前做：

1. `spec_nodes` 出现第二种块来源（插件 / 远程块），需要独立注册协议；
2. 编辑器被第二个前端（非 Streamlit）复用，需要把草稿状态机移出 UI；
3. 评测框架重构时，把 `quality` 的 case/loader/scorer 拆成独立协议；
4. 资源目录需要写入（当前只读），再把 provider 与写适配器分开。

## 6. 验收

- `python -m pytest -q` 全绿；
- 旧入口 `python -m core.quality.stratified` / `python -m core.benchmarks.catalog` 仍可用；
- `python -m core.mcp.resource_server` 可启动并被 MCP client 发现；
- 数据目录在无外置数据时给出明确提示，不因缺文件崩在 import 阶段。
