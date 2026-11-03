# 2026-11-03 改动归档

> 范围：场景可编排（spec）、场景归属（eject）、中间件流水线、自建评测集、复核（judge + 人工）、控制台。
> 验证：`pytest -q` → **174 passed**。

---

## 1. 文件清单

### 场景可编排（spec → LangGraph）

| 文件 | 状态 | 说明 |
|---|---|---|
| `core/scenarios/spec.py` | 新增 | spec schema、结构/参数/策略校验、编译、版本化读写 |
| `core/scenarios/spec_nodes.py` | 新增 | 6 个块 + `ParamSpec` 参数契约 + `react_loop` 复合块 |
| `core/scenarios/flow_demo/` | 新增 | 第 9 个场景，完全由 spec 构建 |
| `data/specs/flow_demo/{v1.json,active.json,state.json}` | 新增 | 版本化 spec、active 指针、归属状态 |
| `tests/test_scenario_spec.py` | 新增 | 33 条：校验、编译、参数契约、策略覆盖 |

### 场景归属（spec-owned / code-owned）

| 文件 | 状态 | 说明 |
|---|---|---|
| `core/scenarios/ownership.py` | 新增 | 状态机、代码 hash、`ensure_spec_editable` 守卫 |
| `core/scenarios/eject.py` | 新增 | CLI：`eject <name> [--reason] [--status]` |
| `AGENTS.md` / `CLAUDE.md` | 新增 | 给编码 Agent 的仓库契约（环境、归属、禁区） |
| `tests/test_scenario_ownership.py` | 新增 | 9 条：hash、漂移、eject、status |

### 中间件流水线（约束式编排）

| 文件 | 状态 | 说明 |
|---|---|---|
| `core/agent/pipeline.py` | 新增 | slot 表、4 条不变量、`PolicySpec`、`build_pipeline` |
| `core/agent/contracts.py` | 修改 | `Scenario.policies` 覆盖层 |
| `core/agent/framework.py` | 修改 | 60 行 if 链 → 一次 `build_pipeline` 调用 |
| `tests/test_pipeline.py` | 新增 | 19 条：8 场景逐层等价、覆盖、不变量 |

### 自建评测集

| 文件 | 状态 | 说明 |
|---|---|---|
| `core/quality/selfbuilt.py` | 新增 | 3 种 kind（retrieval / single / multi）、pass^k、报告 |
| `data/evals/datasets/selfbuilt/tasks.jsonl` | 新增 | 26 条任务 |
| `data/evals/datasets/selfbuilt/NOTES.md` | 新增 | 口径冻结说明、已知漂移、候选校准 |
| `tests/test_selfbuilt.py` | 新增 | 12 条：结构校验、评分、汇总 |

### 复核（LLM judge + 人工）

| 文件 | 状态 | 说明 |
|---|---|---|
| `core/quality/review.py` | 新增 | 构建复核行、judge、标注、汇总、CLI |
| `core/interfaces/dashboard/review.py` | 新增 | 控制台复核视图（唯一 UI 实现） |
| `app_review.py` | 新增 | 独立启动入口，只调同一份 `render_review` |
| `tests/test_review.py` | 新增 | 8 条：构建、标注、分歧、汇总 |

### 控制台与文档

| 文件 | 状态 | 说明 |
|---|---|---|
| `core/interfaces/agent_dashboard.py` | 修改 | 新增「🧾 复核」视图；基础视图 6 → 7 |
| `tests/test_dashboard_smoke.py` | 修改 | 冒烟列表加入 review |
| `README.md` / `docs/PROJECT.md` | 修改 | 视图数 6 → 7，补「复核」 |
| `docs/design/middleware-pipeline.md` | 新增 | 中间件为什么这么排 |
| `docs/design/visual-scenario-roundtrip.md` | 新增 | spec / eject / 演示脚本 |
| `docs/design/lowcode-scenario-layer.md` | 新增 | 低代码范围与推迟决定 |
| `docs/interview/friday-plan-2026-11-06.md` | 新增 | 讲法 + 验证方案 + 时间表 |
| `docs/interview/one-page-2026-11-04.md` | 修改 | 标注改期、修正数字（84→169、6→7） |

### 仓库外（`E:\CODE\benchmarks`）

- `README.md`：13 个数据集的类型 / 判分依赖 / 许可 / 缺口；
- `analyze_mint.py` + `mint_failure_summary.md`：mint-bench 失败模式统计。

---

## 2. 行为变化

1. **装配路径唯一**：所有场景（代码 / spec）都走 `build_pipeline`，`framework.py` 不再有装配知识。
2. **新增第 9 个场景** `flow_demo`，由 `data/specs/flow_demo/` 驱动。
3. **归属单向门**：改 `core/scenarios/flow_demo/` 却未 eject → 构建抛 `OwnershipError`（附命令）。
4. **控制台 7 个基础视图**（新增复核），`coding_demo` 仍多一个运行窗口。
5. **自建集 + 复核**：跑分 → judge → 人工标注，三方分歧单独统计。

---

## 3. 已验证

| 项 | 结果 |
|---|---|
| 全量测试 | 174 passed |
| 8 场景中间件顺序 | 与重构前逐层一致（基线快照对比） |
| `flow_demo` | 编译通过；真实运行产出带 `[seed/agent_harness_notes]` 引用 |
| 归属守卫 | bootstrap → 改代码 → `OwnershipError` → 还原 → 恢复通过 |
| judge 复核 | 4 条多轮结果：auto 4/4、judge 4/4、分歧 0 |
| 控制台 | AppTest 渲染无异常；复核视图含 5 个按钮/条 |

---

## 4. 遗留问题处理（2026-11-03 晚）

| # | 问题 | 状态 |
|---|---|---|
| 1 | `request_timeout` 不生效 | ✅ 已修：`core/llm/factory.py` 构造时传，`config/rag.yml` 新增 `request_timeout: 60` |
| 2 | 自建集 9 条与既有 cases 同题 | ✅ 已重抽：行为层无同题；仅 2 条检索跨层复用（见 NOTES.md） |
| 3 | 自建集未接 gate | ✅ 已接：`selfbuilt pass ≥ 0.60`，报告缺失时 gate 报 missing |
| 4 | workspace 两条多轮未跑通 | ✅ 已跑通：2/2 |
| 5 | CRAG LFS / mint-bench outputs | ✅ 已清理：删除 1.58 GB outputs 与 CRAG 骨架（2969 → 1384 MB） |

遗留：自建集全量基线 **22/26（84.6%，1 trial）**——检索 7/10、单轮 9/10、多轮 6/6；`gate` 已含 `selfbuilt pass 84.62% ≥ 60%` 并通过。稳定性仍需 `--trials 3` 复跑。

---

## 5. 复现命令

```powershell
conda activate langchain

# 测试
python -m pytest -q                      # 174 passed

# 场景归属
python -m core.scenarios.eject flow_demo --status
python -m core.scenarios.eject flow_demo --reason "..."   # 单向门，慎用

# 自建集
python -m core.quality.selfbuilt --scenario robot_vacuum
python -m core.quality.selfbuilt --kind multi_turn --trials 3

# 复核
python -m core.quality.review build --run outputs/selfbuilt/selfbuilt_xxxx.json
streamlit run app_agent.py               # 控制台 → 🧾 复核
```

---

## 6. 关于提交

`git status` 显示 **101 个改动文件**，其中包含本次之外的既有改动（README、dashboard 其他视图、experiments 等）。
建议只 add 上面清单里的文件，或按模块分几次提交：

```text
feat(spec): 场景可编排 + flow_demo
feat(ownership): eject 单向门 + AGENTS 契约
refactor(pipeline): 中间件约束式编排
feat(eval): 自建任务集 + judge/人工复核
feat(dashboard): 复核视图
docs: 设计说明与面试材料
```

未提交，等你确认范围。
