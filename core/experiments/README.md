# 最小 Agent Harness 优化循环 Demo

> 结果总览见 [docs/benchmarks/current-results.md](../../docs/benchmarks/current-results.md)。
> 3 倍样本 / 3 trial 的最终复盘见 [docs/benchmarks/optimization-loop-3x.md](../../docs/benchmarks/optimization-loop-3x.md)。
> 当前最佳组合：`bfcl_fixes`，BFCL 60/60（两轮 3-trial 复跑）、RAG 44/45，0 回归。
> 小样本首轮复盘见 [docs/benchmarks/minimal-optimization-loop.md](../../docs/benchmarks/minimal-optimization-loop.md)。

用两个公开数据集跑一个完整的“跑 → 归因 → 改 → 复跑 → 查回归”循环：

- **BFCL v4**：工具调用，工具实现为 stub，评分看工具名/参数；
- **MultiHop-RAG**：609 篇语料，评分看是否召回 evidence title。

## 命令

```bash
python -m core.experiments.optimize --iterations 5 --trials 3
```

可调参数：

```bash
--bfcl-simple 45        # simple_python 条数
--bfcl-irrelevance 15   # irrelevance 条数
--multihop-per-type 15  # 每个问题类型抽 15 条
--trials 3              # 每个 case 跑 3 次，报 pass^k 和 mean
--configs baseline,routed_prompts,hybrid,english_embedding,arg_validation
--families bfcl,rag     # 只跑某一类，便于快速 A/B
--seed 42
--out outputs/demo
```

## 流程

```text
加载 BFCL / MultiHop 样例
  → FrameworkAgent 执行
  → 失败分类（no_call / wrong_name / wrong_args /
              extra_call / unnecessary_call / retrieval_miss）
  → 同类任务通过率
  → 定向改 prompt / k / 检索器
  → 复跑同一批 case
  → 修复 / 回归对比
```

## 优化方向分类

参考公开 Agent 实践，把优化方向先分类，再选本轮能验证的：

| 方向 | 本轮 | 公开参考 |
|:---|:---:|:---|
| A. Prompt routing | Iter 2 | ReAct / tool-use prompting |
| B. Tool design | Iter 5 | tool schema validation |
| C. Retrieval strategy | Iter 3/4 | hybrid retrieval / 英文 embedding |
| D. Query planning | Iter 2 | Self-Ask / RAG-Fusion（routing 内） |
| E. Loop / error handling | Iter 5 | 工具报错回注 + 重试 |
| F. Memory / persistence | 未验证 | checkpoint / 文件持久化，单轮看不出收益 |
| G. Context management | 未验证 | 压缩 / token 预算，长会话才需要 |
| H. Observability | 部分 | 结果已带 trace_id，但未做指标分析 |

## 五轮配置

| # | 改动 | 方向 |
|:---:|:---|:---|
| 1 | baseline：中性 prompt，vector k=4，zh BGE | — |
| 2 | 任务类型路由：simple 强制调用、irrelevance 先判断；comparison/inference 多子查询 | A/D |
| 3 | 向量 + BM25 混合检索，k=8 | C. Hybrid |
| 4 | bge-small-en-v1.5 + vector k=8 | C. English embedding |
| 5 | BFCL 必填参数校验中间件，缺参回注错误 | B/E |

后续针对性实验（可用 `--configs` 选择）：

| 名称 | 改动 | 目标 |
|:---|:---|:---|
| `python_syntax` | 提示乘方用 `**` 而不是 `^` | 修 `simple_python_13/15/16` 的 wrong_args |
| `bfcl_fixes` | 语法提示 + 同工具重复调用抑制 | 同时修语法和 extra_call |
| `hybrid_validation` | hybrid 基础上单独加参数校验 | 隔离校验效果 |

评分侧对数学表达式做等价归一：`2*x**2` 与 `2x**2` 视为同一写法，但 `^` 仍不算 `**`。

### BFCL 修复实验（2026-10-31）

```text
hybrid          55/60
python_syntax   59/60   # 语法提示修复 13/15/16
bfcl_fixes      60/60   # 语法 + 重复调用抑制
hybrid_validation 56/60 # 单独参数校验
```

- 语法提示是稳定收益；
- `simple_python_377` / `irrelevance_236` 的修复更像模型方差，重复调用抑制的独立贡献尚未被证明；
- 两轮独立 3-trial 复跑均为 60/60，详见 [docs/benchmarks/bfcl-fixes.md](../../docs/benchmarks/bfcl-fixes.md)。

## 输出

```text
outputs/demo/iteration_01.json ... iteration_05.json
outputs/demo/report.md
```

报告包含：

- 每轮 BFCL / RAG 通过率；
- 失败类型分布；
- 同类任务通过率；
- 修复与回归 case 列表；
- 本次行动的边界。

## 边界

- BFCL 工具是 stub，不是官方 AST 评分；
- MultiHop 只评检索召回，不评最终回答；
- 默认 BFCL 60（45 simple + 15 irrelevance）+ RAG 45（3 类 × 15），每 case 3 trial；
- 只改 prompt / tool 校验 / 检索器 / embedding，不改模型；
- 文件持久化、上下文压缩属于架构方向，单轮 demo 无法体现指标收益，未纳入轮次；
- 不是 τ² 官方成绩，τ² 需要单独的 adapter。

## P0 / P1 / P2

- **P0**：3 倍样本、3 trial、pass^k、BFCL 可选参数放宽、结果带 trace_id；
- **P1**：任务类型路由 prompt、hybrid BM25、bge-small-en-v1.5；
- **P2**：SQLite checkpoint / trace_id 已接入；τ² adapter 是下一步。

文件持久化验证：

```bash
python -m core.experiments.persistence_demo
```

同一 `thread_id` 两轮对话，第二轮应能记住第一轮的名字。
