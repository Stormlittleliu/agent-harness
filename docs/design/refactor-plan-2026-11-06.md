# 2026-11-06 重构编排：依赖图与分工

> 本轮主 agent 负责拆任务与集成；一个独立 overseer agent 在合并后做全局审计。
> 原则：先建立共享的路径/契约，再并行做互不依赖的数据与资源两条线，
> 最后统一验收。评测只冻结接口，不改打分框架。

## 1. 目标拆解

| 编号 | 目标 | 产出 | 依赖 |
|:---:|:---|:---|:---|
| G1 | 数据集采样移出 core，公开数据外置，仓库只留引用 | `dataset_ops/`、`data/datasets/`、`core.paths`、README | 无（先做） |
| G2 | core 精简/模块化审计 | `docs/design/core-modularity.md`；只做安全拆分 | G1 的路径层 |
| G3 | 统一资源对象 + 本地 MCP server | `core/resources/`、`core/mcp/resource_server.py`、client | 无（与 G1 并行） |
| G4 | 评测接口维护 | CLI/数据集解析兼容、接口测试；不改框架 | G1 |
| G5 | 集成验收 | 全量测试、MCP stdio smoke、文档同步 | G1–G4 |

## 2. 依赖关系

```text
G1 路径层 + 数据外置 ──┬──> G2 core 审计（路径去重）
                       └──> G4 评测接口（数据集解析）

G3 资源目录 ──> MCP server ──> agent 编辑接入

G1 + G2 + G3 + G4 ──> G5 全局验收
```

严格依赖只有：

1. 路径层必须先于数据移动和评测数据解析；
2. MCP server 必须先有资源 catalog；
3. 全局验收必须等前四条线合并。

G2 与 G3 之间没有代码依赖：资源目录只读现有场景/工具，不要求先拆 core。
G4 与 G3 也没有依赖：评测不改资源模型。

## 3. 并行分工

| 角色 | 责任 | 边界 |
|:---|:---|:---|
| 主 agent | 路径层、编排、集成、文档、最终验收 | 不把用户未提交的 `retail_router` 改动纳入提交 |
| 数据 agent | G1：采样迁移、数据外置、兼容 shim | 不改评测打分 |
| 资源 agent | G3：资源模型、providers、MCP server/client、测试 | 不初始化真实模型/网络 |
| overseer agent | G5 前独立审计：接口、循环依赖、测试、风险 | 只读，不改代码 |

## 4. 验收门槛

- 全量 `python -m pytest -q` 通过；
- 旧命令仍可用：`python -m core.quality.stratified --help`、
  `python -m core.benchmarks.catalog --list`；
- MCP server 能 stdio 启动，`resource_list/get/search/kinds` 可调用；
- 无外置数据时，评测命令给出可操作提示，不在 import 阶段崩；
- `git status` 不包含 `data/datasets/` 下的大数据；
- 用户已有 `data/specs/retail_router/*` 不被覆盖或提交。
