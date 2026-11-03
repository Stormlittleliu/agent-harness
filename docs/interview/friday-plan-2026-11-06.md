# 周五面试计划（11/03 晚 – 11/06 下午）

> 面试：2026-11-06（周五）下午。
> 现状：149 passed，9 个场景，spec 编译 / 中间件流水线 / 场景归属均已落地。
> 原则：**先补证据，再补展示**；周五上午只做检查，不学新东西。

---

## 1. 项目怎么介绍

### 1.1 一句话

> 一个可约束、可观测、可回归的 Agent Harness：模型负责决策，框架负责结构、策略和评测。

### 1.2 90 秒稿（背下来）

> "我做的是一个 Agent Harness，不是聊天机器人。起点是 RAG，加了工具之后开始失控：工具选错、参数传错、上下文爆、高风险操作不能直接跑，改完 prompt 也不知道变好还是变坏。
>
> 所以我把模型外面那层做扎实，拆四块：运行时负责 ReAct 循环和中间件；场景层是一个声明式契约，8 个场景共用同一个运行时，加场景不改框架，这条边界用一条 pytest 守着；评测分能力层、行为层、outcome 层；可观测用 trace 把成本、时延、失败点记下来。
>
> 三个能站住的数：workspace 3-trial 5/5、planning policy 12/12（baseline 11/12）、outcome 12/12。
>
> 这两天我在把场景本身变成数据：spec 编译成 LangGraph、存版本、改图不用改代码；一旦有人改代码，构建期强校验会强制 eject，可视化转只读——因为我不想系统里存在两份真相。
>
> 边界：单机、单 Agent、本地语料；没有联网搜索、没有多 Agent handoff、没有多模态。"

### 1.3 三分钟结构（被要求展开时）

1. **架构（60s）**：5 层 + Scenario 契约 + 用测试守边界。
2. **机制（60s）**：中间件 slot 与不变量（权限最外、HITL 在超时外、error 在 retry 外）；错误是 observation。
3. **证明（60s）**：BFCL 语法提示 59/60→60/60，只加参数校验 56/60 还回归 4 条；router 行为 3/4、outcome 4/4 是评分误判。
4. **演进与边界（30s）**：spec/eject/约束式编排；单机单 Agent。

### 1.4 必须出现的五句

1. 模型负责决策，Harness 负责工具、上下文、权限、预算、评测。
2. 错误是 observation，不是崩溃。
3. Transcript 可以撒谎，Outcome 不会。
4. 能表达成 schema 的进 spec，表达不了的留代码；越界就 eject。
5. 顺序由框架保证，参数才交给用户。

### 1.5 不要说的五句

- ❌ BFCL 官方 100% / τ² 测的是我的 Harness
- ❌ 生产级 MCP 网关 / 多 Agent 平台 / 多模态 Agent
- ❌ 真实客服系统 / 线上用户 / 业务 KPI
- ❌ "可视化编排平台已经做完"（目前只有后端 + 只读图）
- ❌ "评测能抓到图编辑的错误"（cases 跑的是 Agent，不是工作流）

---

## 2. 高性价比验证方案（按 ROI 排序）

| # | 事项 | 工时 | 拿到的证据 | 风险 |
|---|---|---|---|---|
| **V1** | **机器人域检索集 40 条**（从 `故障排除.txt` 200 条机器生成 + PDF 抽 10 条） | 2h | Hit@4 / MRR，vector vs hybrid 对比；替掉"42 条是服装域"的硬伤 | 低 |
| **V2** | **行为用例 13 → 20 条**（耗材周期 / 回充失败 / 边刷缠绕 / 噪音 / 续航衰减 / 保修拒答 / 多轮追问 / 非法参数 ×2） | 2h | 覆盖面 + 通过率；拒答与参数重注入都有实证 | 低 |
| **V3** | **机器人 outcome 3 条**（HITL reject 不执行 reset、approve 执行、报告意图三工具齐全） | 3h | 高风险操作有环境级证据，而不只是"模型说拒绝了" | 中 |
| **V4** | **3-trial pass^k**（20 条 × 3） | 1h | 稳定性数字，替换"单次 13 条" | 低 |
| **V5** | **失败集 3–5 条**（含根因分层） | 1h | 面试追问"举个失败例子"的弹药 | 低 |
| **V6** | 成本/时延按场景切片 | 0.5h | 机器人场景 p50/p95、¥/run | 低 |
| P2 | 编辑 tab（只读 + 表单 + 保存） | 3h | 展示面；没有它新架构只能靠 CLI | 中 |

**如果只有 4 小时**：V1 + V2 + V4。

---

## 3. 为什么先做扫地机器人

它是唯一同时具备五件事的场景：

```text
结构化知识（故障排除 200 条 + 100问 PDF + 维护 + 选购）
+ 外部数据（data/external/records.csv）
+ 高风险操作（reset_device，HITL）
+ 拒答用例（退货政策不在知识库）
+ 意图路由 + 报告工作流
```

而且它直接对应 JD 的"智能硬件"线。相比之下，服装域 42 条 RAG 与当前知识库不匹配，**不能作为当前结果引用**——这个洞必须先补。

### 3.1 V1 具体做法

- 数据源：`data/knowledge/故障排除.txt`（200 条，格式规整：`N. 故障现象：X；检测：Y；修复：Z`）。
- 生成脚本：解析 `故障现象/检测/修复`，取 30 条 → `question = "机器人<故障现象>怎么办？"`，`expected_sources = ["故障排除.txt"]`，`expected_points` 取"检测"里的关键词。
- 再从 `扫地机器人100问.pdf` 抽 10 条，测 PDF 解析与切片；`选购指南.txt`、`维护保养.txt` 各 5 条做类别平衡。
- 落盘：`data/evals/datasets/robot/retrieval.jsonl`（字段 `id/category/question/expected_sources`）。
- 跑：

```powershell
conda activate langchain
python -m core.quality.runner rag retrieval --dataset data/evals/datasets/robot/retrieval.jsonl --docs-dir data/knowledge --k 4
```

- 输出：`outputs/rag/` 下的 vector vs hybrid 对比报告。

> 注意：这条命令是**临时建库**（从 docs_dir 重新切片、embedding），不依赖现有 Chroma，所以结果可复现。

### 3.2 V2 具体做法

在 `core/scenarios/robot_vacuum/cases.jsonl` 追加：

- 耗材：滤网/边刷更换周期（RAG）
- 故障：回充失败、边刷缠绕、噪音变大、续航下降（RAG，对应新增知识条目）
- 拒答：保修期限、上门安装（知识库没有 → should_refuse）
- 参数：`查询用户 99 号的使用记录`（user_id 非法 → 触发重注入）、`2024-13 月的记录`（月份非法）
- 多轮：先问"X1 适合多大面积"，再问"那它续航够吗"（同一 thread）

### 3.3 V3 具体做法

在 `core/quality/outcome_eval.py` 的 robot 分支加断言：

1. `reset_device` + reject → trace 里**没有**成功执行的 tool 事件；
2. `reset_device` + approve → trace 里有，且最终回答确认已重置；
3. "生成使用报告" → 回答里同时出现用户 ID、月份、CSV 数据三类信息（`fetch_external_data` 真的被调用）。

---

## 4. 到周五的时间表

| 时段 | 内容 | 产出 |
|---|---|---|
| 周二晚 1.5h | V1 生成检索集 + 跑 vector/hybrid 基线 | 第一个域内数字 |
| 周三 6h | V2 用例扩充 → V3 outcome → V4 3-trial | 行为/环境两层证据 |
| 周四 5h | 编辑 tab（若还有时间）/ V5 失败集 / V6 成本切片 / 录屏 | 展示面 + 兜底 |
| 周四晚 | demo dry-run 两遍 + 90 秒稿三遍 | 冻结 |
| 周五上午 1.5h | preflight：pytest、flow_demo --status、dashboard 冷启动 | 不学新东西 |

---

## 5. 明确不做

- ❌ 把 8 个场景改写成字面量 `policies`（收益是审美，风险是回归）
- ❌ 条件边 / 手拼 ReAct 循环
- ❌ 拖拽画布、多 Agent、多模态、OTel
- ❌ 面试前一天加新功能

---

## 6. 一句话

> **V1 补的是"域内可信度"，V2 补的是"覆盖面"，V3 补的是"副作用证据"。三样都做完，机器人场景就是全项目最硬的一块证据，而不是最大的窟窿。**
