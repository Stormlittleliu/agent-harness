# 已知妥协与评测债

> 目的：把“曾经这么做”与“现在仍然合理”分开。
> 每条都带证据、风险和下一步；不把历史选择当成设计依据。
>
> 审计日期：2026-11-04。

## P0：会直接影响结论可信度

### 1. `selfbuilt` 复用产品场景，而不是按任务造场景

**证据**：`core/quality/selfbuilt.py:242` 直接 `get_scenario(name)`；`data/evals/datasets/selfbuilt/tasks.jsonl` 26 条里有 18 条 `scenario=robot_vacuum`。

**后果**：任务实际跑的是产品的完整 prompt、工具池、意图路由和 13 条业务 case 的上下文。测的是“任务能不能塞进 robot_vacuum”，不是“这条任务在合适工具下能不能做对”。跨场景数字（22/26）也不能区分“任务难”还是“场景不匹配”。

**下一步**：`core/quality/fixtures.py` 的 `TaskFixture`；已迁 `robot_vacuum` 的 8 条单轮/多轮（8/8），
10 条 retrieval 留在能力层；`research_assistant` / `coding_demo` / `router` / `workspace_assistant`
的任务定义还缺前置工具，先不硬迁。产品场景保留做端到端回归，不再冒充任务级评测。

**2026-11-05 已切**：`selfbuilt.py` 的单轮/多轮已改走 `TaskFixture`，`retrieval` 仍直调 `rag_retrieve`；
`build_selfbuilt_fixtures(scenario="all")` 覆盖 16 条；`sb-multi-005` 已加
`extra_tools: ["remember"]` 和任务级 system_prompt。全量 1-trial **26/26**（报告
`outputs/selfbuilt/selfbuilt_20261105_192922.json`）；这是单次结果，不是 3-trial 稳定性结论。

### 2. 质量页的 benchmark 目录是旧快照

**证据**：`data/benchmarks/manifest.json` 生成于 `2026-10-31`，只有 8 个源、320 条；现在适配器已有 11 个（新增 CFBench / HumanEval / MBPP）。`core/interfaces/dashboard/catalog.py:224` 硬编码“8 个来源”，`ADAPTER_PATHS` 也没有这三个新适配器。

**后果**：页面显示的不是当前能力；新增的 3 个源在目录里不存在。这比“少显示”更糟：它会让人以为已经覆盖了。

**下一步**：重建 catalog；来源数改成 `source_count`；补 `ADAPTER_PATHS`。重建前页面必须标注 `manifest.generated_at` 和数据版本。

**2026-11-05 已修**：`--list` 不再加载数据；`build` 有 `[load]` 进度/单源跳过；`git_version` 缓存；catalog 为 11 源 / 132 条，`manifest.source_count=11`，页面按 `by_runner` 显示执行方式。

### 3. judge 可以覆盖确定性失败

**证据**：`core/quality/agent_eval.py:110-112`：

```python
passed = deterministic["passed"]
if judged is not None:
    passed = judged.get("verdict") == "pass"
```

**后果**：工具没调、参数错，只要 judge 说“回答得不错”，这条就过了。judge 本来只该判语义覆盖，不该覆盖工具/参数这类硬失败。

**下一步**：改成“确定性硬失败优先”；judge 只在确定性通过后做加分/降级，或单独记 `judge_pass`，不覆盖 `passed`。

**2026-11-05 已修**：`passed = deterministic_passed and judge_pass`，新增 `judge_pass` 字段和回归测试。

## P1：口径容易被讲大

### 4. `eval_scope` 是源级映射，不是 case 级判断

**证据**：`core/quality/eval_layers.py` 的 `SOURCE_META` 按 benchmark 名写死；`selections.jsonl` 每条只是复制这个映射。

**后果**：一个源里如果混了“纯能力”和“工具/场景”两种 case，会被整体打成一个标签。GAIA 就是例子：设计上是 `scenario_tool`，但当前适配器只带题面，执行状态是 `tools_required`。

**下一步**：`TaskFixture` 自带 `eval_scope`；源级映射只做默认值，不做最终结论。

### 5. “场景/工具 300 条”里大部分跑不了

**证据**：`manifest.json` 的 `execution` 分布：`harness_required` 285 条（BFCL 95 + τ² 20 + SWE 53 + WebArena 47 + OSWorld 70），`tools_required` 15 条（GAIA），真正 `native` 的只有 RGB 30 + MultiHop 20。

**后果**：300 这个数字听起来像“有 300 条场景/工具评测可跑”，实际只有 50 条能直接跑，而且都是能力层。

**下一步**：对外只报“按 execution 分组”的数；`scenario_tool` 后面必须跟 `harness_required` 的拆分。

### 6. `BenchTask.tools` 只有 BFCL 真的有工具

**证据**：`bfcl.py` 写 `tools=item.get("function")`；`tau2.py:87` 写 `tools=[]`；GAIA/SWE/WebArena/OSWorld 也没有可执行工具。

**后果**：“按任务配工具”目前只对 BFCL 直接成立；τ² 的工具在官方 env，SWE/WebArena/OSWorld 的“工具”其实是环境动作。把同一套 fixture 套到所有族会造出空壳。

**下一步**：每族一个 `TaskToolAdapter`；BFCL 先做，τ² 包官方 env，其余族明确标 `environment_required`，不硬凑。

### 7. `runner.py` 的 benchmark runner 多数是占位

**证据**：`NativeRunner` 对 RGB/MultiHop/GAIA 返回 `native_adapter_required`；CFBench 是 `JudgeRunner`（`judge_required`）；HumanEval/MBPP 是 `SandboxRunner`（`sandbox_required`）。

**后果**：`run_task()` 看起来是统一入口，实际没有任何一条能从头跑到尾。它现在的作用是“说明为什么不能跑”，不是 runner。

**下一步**：要么实现，要么把 `run_task` 标成 `probe`，不要放在“可执行”语义下。fixture 层不要依赖它。

## P2：一致性与可维护性

### 8. spec 不能声明新工具

**证据**：`core/scenarios/generic.py:7-10`：工具只能引用 `pools.toolbox()` 里已有的名字。

**后果**：低代码场景只能组合现有工具；为评测临时配工具必须写代码。`TaskFixture` 因此走代码层，不走 spec，这是有意的，不是漏做。

**下一步**：保持 spec 只管产品结构；评测工具走 `ToolStub` 注册表，不塞进 spec。

### 9. `robot_vacuum` 的关键工具是随机的

**证据**：`core/tools/business/tools.py:39/44/49`：`get_user_location`、`get_user_id`、`get_current_month` 都 `random.choice`；case 用宽正则兜底。

**后果**：3-trial 的 `pass^k` 会被随机性污染；某次失败可能只是随机到了没覆盖的分支。产品演示没问题，评测需要可控。

**下一步**：fixture 用固定 seed/固定返回值；产品场景保留随机，但评测报告要标“产品随机工具”。

### 10. 出处记录写的是绝对路径

**证据**：`data/evals/datasets/stratified/selections.jsonl` 的 `source` 是 `E:/CODE/benchmarks/...`。

**后果**：换台机器、换盘符就无法按记录复现；仓库里留着一份“只有作者本机能用”的 provenance。

**下一步**：存 `benchmark` + 相对路径 + `BENCHMARK_ROOT` 版本；绝对路径只放本地 manifest，不进仓库。

**2026-11-05 已修**：`stratified.py` 写 `source` 时改为相对 `DEFAULT_BENCH_ROOT`，并写
`source_root: BENCHMARK_ROOT`；现有 `selections.jsonl` 381 行已重写，`absolute_left=0`。

### 11. 文档里的测试数已经过期

**证据**：`AGENTS.md:8` 当时写“当前 283 passed”；`docs/design/plan-status.md:25` 写“365 passed”；审计时是 375。现在以 399 为准。

**后果**：读文档的人会拿旧数字做判断；面试时被问“多少测试”会答错。

**下一步**：测试数只在一个地方维护（例如 `README` 徽章/CI），其他文档引用链接，不写死。

**2026-11-05 已修**：AGENTS / README / 一页纸 / friday-plan 的当前数字同步为 408 tests、11 场景；历史快照保留但标注过期。

### 12. 质量页的 benchmark 视图只认 BFCL / RGB / τ²

**证据**：`core/interfaces/dashboard/benchmarks.py:331-336` 的 `st.radio` 只有三项；CFBench / HumanEval / MBPP 没有入口。

**后果**：新接的源只能在 catalog 里看到，不能在质量页按 benchmark 看；看起来像没接。

**下一步**：要么把新源并进 catalog 视图，要么在 benchmark 视图加“其他”分组；先补数据，不急着加 tab。

**2026-11-05 已修**：公开基准页加「其他（仅目录）」分组，只读 `manifest.json`，明确标注“只有数据、没有报告”。

### 13. 根 README 的规模与结果数字过期

**证据**：`README.md` 写“8 个场景 / 40+ 工具”（实际 9 个场景、47 个唯一工具）；写“research 2/3、router 3/4”，而 `outputs/agent/` 最近报告是 research 3/3、router 4/4；还写“44 条行为用例”，实际各场景 cases 合计 45。

**后果**：面试官按 README 问，数字对不上；旧结果被当成当前结果。

**下一步**：README 只保留“怎么跑 + 指向最新报告”，具体数字从 `outputs/*` 读取；不把一次性结果写死在介绍页。

### 14. 统一 catalog 的构建命令没有进度和超时

**证据**：`python -m core.benchmarks.catalog --list` / `--build` 在本机跑超过 2 分钟没有任何输出；`core/benchmarks/catalog.py` 是串行 `adapter.load()`，没有 per-adapter 超时、没有进度。`data/benchmarks/` 因此停在 2026-10-31 的 8 源快照。

**后果**：新 adapter 加进来后，目录页无法可靠刷新；“统一 catalog”实际上是一次性脚本，不是可重复构建。

**下一步**：每个 adapter 加超时和 `[load] name` 即时 flush；失败只跳过该源并记录，不拖死整批。

**2026-11-05 已修**：`--list` 只查可用性；`build` 每个源 flush 进度、异常跳过并记 `error`；根因是 `git_version` 每条任务跑一次 git，已按仓库缓存。重建耗时从“看起来卡死”降到秒级。

## 这次先动什么

1. **新增 `core/quality/fixtures.py`**：`TaskFixture` / `ToolStub` / `clean|distractor|missing|failure|permission`，先做 BFCL POC。
2. **permission 用真实 HITL**：`reset_device` 的 approve / deny 两条路径，不伪造。
3. **审计文档就是这份**；P0/P1 不在一晚全修，但不再假装它们不存在。

## 本次已落地（2026-11-05）

- `core/quality/fixtures.py` + `docs/design/eval-fixtures.md`；
- BFCL POC：10 条任务 × 4 变体 = 40 条，32/40；clean/distractor/failure 均 10/10，
  失败集中在 `missing` 2/10（无工具时模型直接心算，不说明“工具不可用”）——这是要抓的幻觉；
- permission：approve ✅、reject ✅（真实 HITL 中断 + resume）；
- selfbuilt 迁移：`robot_vacuum` 8 条单轮/多轮 fixture **8/8**；
- 测试：408 passed。

## 2026-11-05 晚二次修复

- **P0-2 / P1-14 catalog**：`--list` 不再加载全量数据；`build` 每个 adapter 先 flush
  `[load]`，单源失败跳过并记 `error`；`git_version` 按仓库缓存，不再每条任务跑一次 git。
  重建后 catalog 为 **11 个来源 × 12 = 132 条**，manifest 带 `source_count` / `by_runner`。
- **P0-3 judge**：确定性硬失败优先；judge 只会在确定性通过后确认/降级，新增
  `judge_pass` 字段和回归测试。
- **P1-4 eval_scope**：`TaskFixture` 自带 `eval_scope`，结果行带上该字段；源级映射只做默认值。
- **P1-7 runner**：`run_task` 明确是 probe；占位 runner 返回 `probe=True`，不把
  `*_required` 当执行结果。
- **P1-11 / P1-13 文档口径**：AGENTS 测试数、README 场景/用例数、ARCHITECTURE / PROJECT
  的 catalog 数同步为当前值。
- **新场景**：`clothing_service` 6 条、`retail_router` 5 条行为用例；3-trial pass^k 分别 **6/6**、**5/5**。
- **branch**：支持 `cases` 多路 + `default`，旧 `hit/miss` 兼容；编译期校验
  “branch 可能写出的 route 必须有对应条件边”。同时修正了 robot_vacuum / workspace_assistant
  旧 spec 里 `branch` 写 `verify/answer`、边上却写 `miss` 的真实错位。

## 仍未修

- P1-5 “300 条里大部分跑不了”的对外口径已改为按 `by_runner` 分组，但 60 条任务级样本
  仍不能代表全量；这是数据事实，不是待修 bug。
- P1-6 除 BFCL 外，多数族的 `BenchTask.tools` 仍为空；要接 `TaskToolAdapter` 或官方环境。

P1-1 / P1-10 / P1-12 已在 2026-11-05 处理：selfbuilt 已切任务级 fixture，
provenance 已改相对路径，公开基准页已有「其他（仅目录）」。


## 不打算改的

- `stratified` 原始样本不提交：RGB 是 CC BY-NC-SA，这是许可约束，不是妥协。
- `spec` 不能声明工具：这是产品/评测分层的刻意边界，不是缺口。
- 产品场景继续保留随机工具：演示需要多样性；评测用 fixture 固定。
