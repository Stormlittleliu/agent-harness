# 最小 Harness 优化循环：本次运行复盘

> 这是 **小样本首轮（BFCL 20 + RAG 15，1 trial）** 的复盘。
> 扩到 3 倍样本 + 3 trial 的 P0/P1 运行见 `outputs/demo/report.md`。

> 运行：2026-10-31，seed=42，DeepSeek `deepseek-chat`
> 数据：BFCL v4（15 simple + 5 irrelevance）、MultiHop-RAG（comparison / inference / temporal 各 5 条）
> 代码：`core/experiments/optimize.py`
> 原始报告：`outputs/demo/report.md`

## 1. 结果总览

| # | 方向 | 改动 | BFCL | RAG Hit@4 | 修复 | 回归 |
|:---:|:---|:---|:---:|:---:|:---:|:---:|
| 1 | baseline | 中性 prompt；vector k=4 | 18/20 | 11/15 | 0 | 0 |
| 2 | A. Prompt | 强制调用工具；回答前必须检索 | 17/20 | 11/15 | 0 | 1 |
| 3 | C. Retrieval | k 4→8 | 18/20 | 10/15 | 1 | 1 |
| 4 | D. Query planning | 多跳多子查询 | 18/20 | 10/15 | 0 | 0 |
| 5 | B/E. Tool & error | 必填参数校验 + 缺参回注 | 18/20 | 10/15 | 0 | 0 |

结论：**这次没有找到稳定正向的优化；循环本身跑通了，但暴露出评测口径、prompt 冲突和检索瓶颈。**

## 2. Badcase 归因

### 2.1 BFCL `simple_python_379`：不是模型错，是评分口径

```text
期望：get_current_time(location="Sydney", country="Australia", timezone="")
实际：get_current_time(location="Sydney", country="Australia", timezone="Australia/Sydney")
```

`timezone` 在 ground truth 里是可选参数，候选值为空字符串；模型补了一个合法时区。
简化评分把“多填可选参数”判成 `wrong_args`。

- 归因：**评分定义**，不是 Harness 或模型能力；
- 同类观察：其他 14 条 simple 都通过，只有这一条受可选参数影响；
- 下一步：明确“可选参数填了合法值算不算错”，或按官方 BFCL scorer 处理。

### 2.2 BFCL `irrelevance_8`：真正的过度调用

```text
问题：What is 0x128 as a decimal?
实际：调用 str_to_int(value="156")
```

- 归因：模型在无关任务上仍然调用工具；
- 第 2 轮强制“必须调用工具”后，`irrelevance_59` 也出现过度调用，BFCL 从 18 降到 17；
- 同类观察：irrelevance 5 条中，baseline 4/5，强制 prompt 后 3/5；
- 结论：**一个全局 prompt 不能同时服务 simple 和 irrelevance**，应按任务类型路由 prompt。

### 2.3 MultiHop comparison：检索瓶颈，不是查询次数

以 `multihop-comparison_query-0` 为例：

```text
问题：TechCrunch vs CNBC 对 SBF 动机的报道是否不同
baseline 已经调用 4 次 rag_retrieve，query 分别覆盖 TechCrunch / CNBC / board / governance
检索到的都是 SBF 相关文章，但没有命中 evidence title
```

`comparison_query-4` 同样：已经调用 6 次，检索到 Vikings/NFL 文章，但没命中指定 evidence。

- 归因：**检索召回**，不是 query 数量；
- 同类观察：baseline comparison 3/5，k=8 后 2/5，inference 4/5、temporal 4/5 稳定；
- 现有配置是中文 BGE + 英文语料，本身是弱配置；
- 下一步优先级：英文 embedding / hybrid BM25 / rerank，而不是继续加 query。

### 2.4 k=8 与 multi-query 的“无效”

- k=8 只改变 retriever 返回条数，评分只看每次调用前 4 条；理论上 top-4 不变；
- 观察到的 RAG -1 更可能来自**单次运行的模型随机性**，不是 k 的真实效果；
- multi-query prompt 没有带来新增调用，因为 baseline 已经在多 query；
- 这说明：**单 trial 对比不足以判断改动是否有效**，需要每个 case 跑 3 次。

### 2.5 参数校验中间件没有触发

第 5 轮加了必填参数校验，但 20 条 BFCL 里没有“缺必填参数”的 case，所以指标不变。

- 归因：**机制没有被坏样本触发**；
- 下一步：专门造 fault-injection case（缺参数、错类型、工具超时），否则无法证明中间件有效。

## 3. 优化方向结论

| 方向 | 本次结果 | 判断 |
|:---|:---|:---|
| A. Prompt / instruction | BFCL -1，RAG 0 | 全局强制调用会伤害 irrelevance；应改为按任务类型路由 |
| B. Tool design | 0 | 校验机制没被触发；需要 fault-injection 样本 |
| C. Retrieval strategy | RAG -1（疑似噪声） | k 不是瓶颈；应换英文 embedding / hybrid / rerank |
| D. Query planning | 0 | baseline 已在多 query；瓶颈在召回 |
| E. Loop / error handling | 0 | 缺少能触发错误的样本 |
| F. Memory / persistence | 未验证 | 单轮 demo 看不出收益；多轮/恢复场景才有意义 |
| G. Context management | 未验证 | 长会话才需要 |
| H. Observability | 未验证 | 生产环境必需，非任务指标 |

## 4. 下一版整体优化方案

### P0：先把评测做对

1. **每个 case 跑 3 trial**，报 pass^3 / 均值 + 置信区间；
2. BFCL 可选参数口径统一，或改用官方 scorer；
3. 增加 fault-injection case：缺参数、错类型、工具超时、工具异常；
4. 把“修复/回归”从单次对比改成 paired 对比（同一 case 多次）。

### P1：按任务类型拆分策略

1. simple：强制工具调用 + 参数提示；
2. irrelevance：不强制调用，增加“先判断是否需要工具”的提示；
3. comparison：英文 embedding / hybrid BM25 / rerank；
4. 其他类型：保持 baseline，避免被全局 prompt 误伤。

### P2：Harness 能力

1. 多轮/恢复：checkpoint + 文件持久化（对应 F 方向）；
2. trace 记录每次工具调用和错误回注（对应 H 方向）；
3. 把同样的循环接到 τ² adapter，测真实多轮任务；
4. 把 outcome 断言（DB/state）接进回归集。

## 5. 本次行动的边界

- 样本：BFCL 20（15 simple + 5 irrelevance）、MultiHop 15（3 类 × 5）；
- 工具：BFCL 是 stub，只评工具名/参数；MultiHop 只评检索召回；
- 评分：简化评分，不是 BFCL 官方 AST，也不是 τ² 官方 reward；
- 运行：单 trial，结论不声明统计显著；
- 改动：只改 prompt / 参数校验 / k，没有改模型；
- 未验证：文件持久化、上下文压缩、trace、真实多轮环境。

一句话：

> 这次循环的价值不是“把分数刷上去”，而是证明了 **badcase 归因必须先分清：是模型、是评分口径、是 prompt 冲突，还是检索瓶颈**。分不清这四类，优化就会在噪声里打转。
