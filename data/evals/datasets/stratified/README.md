# 分层抽样集（每类 5 条）

> 这里不是官方 benchmark 成绩，也不是用来替代现有评测集的。
> 它只解决“现有抽样覆盖不均”的问题：BFCL 只测两类、RGB 只有中文
> refine/int/fact、τ² 只有 retail。

## 文件

| 文件 | 内容 |
|---|---|
| `bfcl_5per_category.jsonl` | BFCL v4 的 19 个类别，每类 5 条 |
| `rgb_5per_category.jsonl` | RGB 中/英 × normal/integration/counterfactual，每类 5 条 |
| `tau2_5per_domain.jsonl` | τ² 的 airline / banking / retail / telecom，每域 5 条 |
| `multihop_5per_type.jsonl` | MultiHop 的 4 个 question_type，每类 5 条 |
| `cfbench_5per_split.jsonl` | CFBench 的 easy/hard × 是否可回答，每类 5 条 |
| `gaia_5per_level.jsonl` | GAIA validation 的 3 个难度，每级 5 条 |
| `humaneval_5per_task.jsonl` | HumanEval 单组 5 条 |
| `mbpp_5per_task.jsonl` | MBPP 单组 5 条 |
| `swebench_5per_repo.jsonl` | SWE-bench 按 repo 分组，每 repo 5 条 |
| `webarena_5per_site.jsonl` | WebArena 按站点组合分组，每组 5 条 |
| `osworld_5per_category.jsonl` | OSWorld 按应用/任务类别，每类 5 条 |
| `selections.jsonl` | **逐条出处**：源文件、源 hash、源行号、源 id |
| `selections.md` | 按类别汇总的出处表 |
| `manifest.json` | seed、每类目标、各集合计数与源规模 |

> `*_5per_*.jsonl` 是从本地 benchmark 源生成的原始样本，**不随仓库分发**
> （RGB 源数据是 CC BY-NC-SA，不能直接塞进 MIT 仓库）。
> 仓库只保留 `selections.jsonl` / `selections.md` / `manifest.json` 作为出处记录；
> 在本地跑一次生成命令即可还原原始样本。
>
> 当前（seed=42，每类 5 条）共 **381 条**：BFCL 95、RGB 30、τ² 20、MultiHop 20、
> CFBench 21、GAIA 15、HumanEval 5、MBPP 5、SWE-bench 53、WebArena 47、OSWorld 70。
> GAIA/SWE-bench/WebArena/OSWorld 走现有 BenchTask 适配器，`source_index` 为空，
> 用 `source_id`（task id）溯源；新增的 CFBench / HumanEval / MBPP 有原始行号。

## 判分口径：模型能力 / 场景工具

| 口径 | 条数 | 集合 | 怎么判 |
|---|---:|---|---|
| **模型能力** `model_capability` | 81 | RGB 30、MultiHop 20、CFBench 21、HumanEval 5、MBPP 5 | 只看最终输出（文本/代码/答案）；不检查工具调用或环境状态 |
| **场景/工具** `scenario_tool` | 300 | BFCL 95、τ² 20、GAIA 15、SWE 53、WebArena 47、OSWorld 70 | 要看工具选择/参数、多轮对话或环境终态；最终输出对不算通过 |

`selections.jsonl` 每条都带 `eval_scope` 和 `execution`。这两个字段不是一回事：

- `eval_scope`：这条 case **该怎么判**；
- `execution`：本仓库**现在能不能跑**。

| execution | 含义 | 当前集合 |
|---|---|---|
| `native` | 已有本项目的 runner / 报告路径 | RGB、MultiHop |
| `judge_required` | 要 LLM judge，尚未接 | CFBench |
| `sandbox_required` | 要代码执行沙箱，尚未接 | HumanEval、MBPP |
| `harness_required` | 要官方 harness / 环境，只做了数据适配 | BFCL、τ²、SWE-bench、WebArena、OSWorld |
| `tools_required` | 题面需要联网/文件/工具，但适配器没带工具 | GAIA |

所以“场景/工具 300 条”不等于“能跑 300 条场景/工具评测”；大部分是
`harness_required`。GAIA 归到场景/工具，是因为官方任务要联网/读附件；但当前
适配器只带题面，所以执行状态是 `tools_required`。

## 抽样规则

- seed = 42，每类 5 条；
- 先按源 id 排序，再用 `seed + category` 随机抽样，不是取前 5 条；
- BFCL 的 `format_sensitivity` 是索引文件，没有题目正文，跳过；
- RGB 没有独立的 rejection 源文件，不伪造该类别；
- MultiHop 的 null_query 保留；全量评测另见 `outputs/public/multihop_full.md`；
- CFBench 的 `doamin` 混了领域和任务类型（200+ 个值），不用它分层；用
  `split` × `isanswer`（是否可回答），1 条缺 `isanswer` 单独成组；
- HumanEval / MBPP 没有官方类别字段，单组 5 条，**不代表覆盖全部难度**。

## 能接 / 不能接

| 源 | 状态 | 原因 |
|---|---|---|
| CFBench | 已接 | `prompt` / `criteria` / `gold` / `isanswer` 已够；判分靠 LLM judge |
| HumanEval | 已接（采样） | 题面和单测都有，但需要代码执行沙箱；runner 返回 `sandbox_required` |
| MBPP | 已接（采样） | 同上；本地只有数据，没有官方 harness |
| API-Bank | 未接 | API 是 Python 类，要写 stub / 执行器；L3 只有 8 个场景说明 |
| MINT | 未接 | 任务在 `mint/tasks/*.py`，工具、反馈循环、预算都在代码里，数据只是 prompt |
| AgentBench | 未接 | `data/` 是环境初始状态，执行在 server + Docker，不是静态 BenchTask |

HumanEval / MBPP 的 `grader` 是 `unit_test`，`environment.runner` 是
`sandbox_required`：**能采样、能溯源，但还不能在本仓库里判分**。不要把它们
写成“已跑通”。

## 重新生成

```powershell
python -m core.quality.stratified --per-category 5 --seed 42
```

重新生成会覆盖本目录的 jsonl / selections / manifest，但不会动
`data/evals/datasets/public/` 下的现有抽样集。
