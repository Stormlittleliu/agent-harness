# 评测接口冻结（2026-11-06）

> 本轮重构**不动评测大框架**：不改 task / trial / scorer / report 的结构，
> 只保证数据外置和 core 路径调整后，外部调用面保持不变。真正的评测框架重构
> 另开一轮，届时这份文档就是迁移基线。

## 1. 冻结范围

### CLI

`python -m core.quality.runner` 的子命令保持：

```text
agent  outcome  rag  public  judge  bfcl  structured  failures  tau2
```

参数可以增加，但不能删除或改语义；`core.quality.runner.main(argv)` 仍接受
显式 argv，方便测试和后续包装。

### 数据

- `core.quality.paths.DATASETS_DIR`：项目自有评测集根（`data/evals/datasets`）；
- `core.quality.paths.dataset_path(...)`：外置数据集解析，优先
  `AH_DATASET_ROOT`，回退旧 `data/evals/datasets`；
- `core.benchmarks.schema.BenchTask` 字段保持：
  `id/source/source_version/split/category/task_type/instruction/grader/environment`
  + `bucket/eval_scope/initial_state/tools/policy/success_criteria/reference/
  difficulty/license/url/metadata`。

### 报告

`core.quality.paths` 里 `AGENT_OUT / RAG_OUT / PUBLIC_OUT / BFCL_OUT /
STRUCTURED_OUT / OUTCOME_OUT / TRACE_OUT` 名称不变；报告仍写 `outputs/`。

## 2. 本轮允许的变化

- 采样实现移到 `dataset_ops/`，旧 `core.quality.stratified` 保留兼容 shim；
- 公开样本移出 git 跟踪，评测运行时通过 `dataset_path` 读取；
- `core/benchmarks/paths.py` 不再写死作者机器盘符，改用 `AH_BENCHMARK_ROOT`；
- 缺数据时命令报“未安装 + 导入方式”，不改变评分逻辑。

## 3. 不在这轮做

- 统一 `EvalCase` / `EvalRun` / `Scorer` 协议；
- 合并 agent / rag / public / bfcl / outcome 的 report schema；
- pass^k、CI、judge 校准；
- 数据集 CRUD / 版本管理 UI。

## 4. 验收

`tests/test_eval_interface.py` 锁住 CLI 子命令、数据集解析和 `BenchTask` 字段；
全量测试通过后，再开始下一轮评测重构。
