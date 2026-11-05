# selfbuilt badcase 与初步优化（2026-11-05）

> 基线：`outputs/selfbuilt/selfbuilt_20261105_192014.json`，全量 1-trial **22/26**。
> 失败 4 条：3 条检索 + 1 条多轮。这里的优化只针对这 4 条，不扩大评测范围。

## 1. 失败清单

| ID | 类型 | 期望 | 实际 | 归因 |
|---|---|---|---|---|
| `sb-rag-001` | 检索 | `故障排除.txt` | 100问2 / 维护保养 | 1000 字 chunk 把多条问答混在一起，宽泛 FAQ 块压过单条故障条目 |
| `sb-rag-006` | 检索 | `维护保养.txt` | 100问.pdf / 100问2 | 同上，维护保养内容被 100问 的宽泛块挤掉 |
| `sb-rag-010` | 检索 | `选购指南.txt` | 100问.pdf / 100问2 | 同上，选购条目没有独立成块 |
| `sb-multi-005` | 多轮 | 覆盖 `pass^k` | 只答 outcome / 成本 / 时延 | fixture 缺 `remember` 前置工具；task prompt 没要求稳定性指标 |

## 2. 初步优化

### 检索：编号型 FAQ 按条目切块

`core/tools/rag/vector_store.py` 新增 `_split_numbered_entries`：

- 对 `100问` / `故障排除` / `选购指南` / `维护保养` 这类 txt，按 `1.` / `2.` 编号边界切；
- 不再合并短条目，避免把编号边界重新抹掉；
- 其他文档仍走原 `RecursiveCharacterTextSplitter`。

重建后：**835 chunks**（原 78），知识库来源分布不变。代价是 chunk 数约 10 倍，
embedding / 检索延迟会上升；这是“单条事实可检索”换来的成本。

### 多轮：补前置工具 + 任务级 prompt

- `sb-multi-005` 增加 `extra_tools: ["remember"]`，先记住偏好再检索；
- task 增加 `system_prompt`，明确要求回答同时覆盖 outcome 与 pass^k / 多次试验；
- `TaskFixture` 支持任务级 `system_prompt`，不借用产品场景 prompt。

## 3. 验证

| 项 | 结果 | 报告 |
|---|---|---|
| 检索 10 条 | **10/10**（原 7/10） | `outputs/selfbuilt/selfbuilt_20261105_192631.json` |
| `sb-multi-005` | **1/1** | `outputs/selfbuilt/selfbuilt_20261105_192443.json` |
| 单轮 10 条 | **10/10**（迁移后） | 基线全量 |
| 全量 26 条 | **26/26** | `outputs/selfbuilt/selfbuilt_20261105_192922.json` |

## 4. 边界

- 检索分数按“期望源文件命中”算，不是最终回答质量；10/10 只说明源文件能召回；
- 835 chunks 是当前本地索引，重建耗时和检索延迟都比原来高；
- `sb-multi-005` 的 task prompt 直接点名了 pass^k，属于“任务要求”，不是通用产品 prompt；
- 这轮只做初步优化；全量 1-trial 26/26 是单次结果，不是 3-trial 稳定性结论。
