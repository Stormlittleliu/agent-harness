# 公开 Agent 基准准备（Agent-first）

> **目的**：用公开、可复现的 Agent 基准替代"自己划分"的评测，作为简历/面试的主证据；自建评测降级为回归集和失败分析。
> **面试方向**：Agent 开发 / LLM 应用工程师，不是 RAG 算法岗。
> **结论**：**τ²-bench 为主，BFCL 为辅；RAG 只是 Agent 的一个工具。**

---

## 1. 为什么调整

当前自建评测的问题：

- 13 条 Agent 用例、42 条 RAG 用例都是自己划分的，面试官无法判断难度和分布；
- RAG 指标占比过高，容易把"客服 Agent"讲成"RAG 项目"；
- Agent 岗位更关心：工具调用、循环/规划、状态、权限、评测、失败恢复，而不是切块参数。

调整后：

| 层级 | 用途 | 证据 |
|:---|:---|:---|
| **主证据** | 公开 Agent 基准 | τ²-bench retail 抽样；BFCL v4 抽样 |
| **辅助证据** | 自建回归集 | 13 条 Agent 行为用例、42 条 RAG 用例 |
| **工具级证据** | RAG 作为工具 | Hit@4 / MRR / 拒答，不再作为项目主标题 |

---

## 2. 公开基准选择

| 基准 | 测什么 | 为什么适合 | 成本/可行性 | 结论 |
|:---|:---|:---|:---|:---|
| **τ²-bench** | 客服多轮：工具 + 业务政策 + 用户模拟器 + pass^k | 和客服 Agent 场景最接近；测的是工具选择、政策遵守、多轮状态 | Python 3.12 + LiteLLM；可用 `deepseek/deepseek-chat` 作为 agent 和 user；retail 114 条 base，released text-v1 每 domain 50 条 frozen | **主基准** |
| **BFCL v4** | 函数调用：选择、参数、并行、无关工具不调用 | 工具调用是 Agent 核心能力；公开且标准化 | 官方支持 DeepSeek-V3.2-Exp-FC；可用官方 checker 或抽样简化评分 | **辅基准** |
| GAIA | 通用助手：多步推理 + 工具 + 文件 | 综合能力强 | HuggingFace 需登录/接受条款；工具环境重 | 可选，暂不做 |
| AgentBench | 8 类环境综合 | 覆盖面广 | Docker 环境重、更新慢 | 不做 |
| WebArena | 网页多步任务 | 接近真实 Web Agent | 自托管网站，环境重 | 不做 |
| SWE-bench | GitHub issue 修复 | Coding Agent 金标准 | Docker + 长跑，方向不匹配 | 不做 |

---

### 2.1 为什么不是 200 条

τ²-bench retail **base split 共 114 条任务**；released `text-v1` 每个 domain 取 **50 条 frozen 任务**；
完整 `text-v1` 是 **6 语言 × 3 domain × 50 = 900 条对话**。

所以：

- 200 条在单一 retail domain 不存在；
- 20 条是抽样，50 条是 released English subset，900 条是全量；
- 每条任务都是多轮对话（agent + user simulator + 工具），20 条已经会产生上百次 LLM 调用。

## 3. τ²-bench 执行方案

### 3.1 环境

- Python 3.12（仓库 `requires-python >=3.12,<3.14`）
- 文本模式不需要 voice extras
- 依赖：`uv sync` 或 `pip install -e .`
- 模型：LiteLLM 字符串 `deepseek/deepseek-chat`
- 环境变量：`DEEPSEEK_API_KEY`
- 用户模拟器：显式指定 `--user-llm deepseek/deepseek-chat`，避免默认 OpenAI 依赖

### 3.2 抽样命令

```bash
# 先 dry-run，确认任务、模型、调用计划
tau2 run --domain retail \
  --agent-llm deepseek/deepseek-chat \
  --user-llm deepseek/deepseek-chat \
  --num-tasks 20 --num-trials 1 \
  --save-to retail_sample --dry-run

# 没有 OPENAI_API_KEY 时，用 DeepSeek 替代 NL judge（非官方口径）
python run_tau2_deepseek_judge.py run --domain retail \
  --agent-llm deepseek/deepseek-chat \
  --user-llm deepseek/deepseek-chat \
  --num-tasks 20 --num-trials 1 \
  --max-concurrency 2 --timeout 600 \
  --communicate-scorer substring \
  --save-to retail20_deepseek_judge
```

- `--domain retail`：零售客服，和项目场景一致；
- `--num-tasks 20`：抽样，不是官方完整分数；
- `--num-trials 1`：先看 pass@1；时间允许再跑 `--num-trials 3` 看 pass^3；
- `--timeout 600`：单任务超时，避免卡死；
- `--max-concurrency`：按 API 限流设置，先 1–2；
- **NL judge**：官方默认是 OpenAI `gpt-5.4-mini`；没有 `OPENAI_API_KEY` 时用
  `run_tau2_deepseek_judge.py` 把 judge 替换成 DeepSeek，分数只能标"非官方"。

### 3.3 指标口径

| 指标 | 来源 | 用法 |
|:---|:---|:---|
| pass@1 | τ²-bench 结果 | "20 条抽样中 X 条通过" |
| pass^k | `--num-trials k` | 时间允许再报 |
| 工具调用 | 轨迹 | 错误工具、参数错误、无效调用 |
| 政策遵守 | evaluation criteria | 是否违反业务政策 |
| 步数/延迟/成本 | 轨迹/日志 | 每条任务的平均步数、耗时、token |

**口径**：抽样没有官方分数，简历写"τ²-bench retail 抽样 20 条，Pass^1 X/20"，不要写"τ²-bench 得分 X%"。

---

## 4. BFCL 执行方案

### 4.1 选择

- 使用 `E:\CODE\benchmarks\BFCL\...\BFCL_v4_simple_python.json` 和 `BFCL_v4_irrelevance.json`；
- 运行 `python -m core.quality.runner bfcl --simple 100 --irrelevance 100`（`core/quality/bfcl.py`）；
- 官方模型 ID：`DeepSeek-V3.2-Exp-FC`（BFCL 支持列表）；
- 如果官方 handler 与当前 API 模型不匹配，退化为"BFCL v4 抽样 + 简化评分"，并在口径里写明。

### 4.2 指标

| 指标 | 定义 |
|:---|:---|
| 工具选择准确率 | 选对函数名 |
| 参数正确率 | 参数名/值符合 ground truth |
| 无关工具误调用率 | irrelevance 样本中调用任何工具的比例 |
| 并行/多工具 | 是否一次调用正确工具集合 |

### 4.3 输出

- `outputs/bfcl/eval_bfcl.md`
- 简历写"BFCL v4 抽样 20 条，工具选择 X/20，无关工具误调用 Y/10"。

---

## 5. Agent-first 叙事调整

### 5.1 项目标题

> ❌ "基于 RAG 的智能客服"
> ✅ "客服 Agent Harness：工具编排、权限审批、状态管理与评测"

### 5.2 架构叙事

```text
用户 → Agent Loop（LangChain create_agent）
        ├── 工具层：知识库检索 / 天气 / 定位 / 用户 / 月份 / 使用记录 / 设备重置
        ├── 状态层：thread_id + Checkpoint
        ├── 权限层：HITL + PII
        ├── 工作流：LangGraph（检索→回答→校验；报告生成）
        └── 评测层：τ²-bench / BFCL / 自建回归集
```

**RAG 是工具层里的一个工具，不是系统本身。**

### 5.3 简历 bullet 顺序

1. Agent 能力：`create_agent`、7 工具、参数校验、HITL、Checkpoint、LangGraph；
2. 评测：τ²-bench 抽样、BFCL 抽样、自建 13 条回归；
3. RAG 作为工具：BGE + Hybrid + 拒答，Hit@4/MRR 作为工具级指标。

### 5.4 面试话术

> "我一开始把重点放在 RAG，后来发现 Agent 岗更看重工具编排、状态、权限和评测，所以把 RAG 降级为 `knowledge_base_search` 工具，主线改成 Agent Harness，并用 τ²-bench / BFCL 做公开基准验证。"

这句话本身就是加分项：说明你会根据岗位调整技术重心。

---

## 6. 一周内的执行顺序

| 顺序 | 任务 | 产出 |
|:--:|:---|:---|
| 1 | 建 τ²-bench Python 3.12 环境，`--dry-run` 验证 | 环境 + 运行计划 |
| 2 | 跑 retail 20 条抽样（1 trial） | pass@1、轨迹、延迟 |
| 3 | 时间允许跑 3 trials | pass^3 |
| 4 | BFCL 20 条抽样 | 工具选择/参数/误调用 |
| 5 | 自建 13 条 / 42 条作为回归集 | 辅助指标 |
| 6 | 更新简历与 2 分钟稿 | Agent-first 版本 |

---

## 7. 风险与边界

- **抽样不是官方分数**：20 条 τ²-bench、200 条 BFCL 都只是抽样，必须写明。
- **DeepSeek 兼容性**：τ²-bench 通过 LiteLLM 调用；先 dry-run，再 1 条 smoke，确认工具调用正常。
- **成本**：τ²-bench 每条任务多轮调用，20 条约几百次 LLM 调用；先用低并发。
- **不混口径**：公开基准、自建回归、RAG 工具指标分开写。
- **不为了分数调 Prompt**：公开基准用于验证，不是刷榜；失败分析比分数更有价值。

---

## 8. 一句话

> **Agent 岗的主证据是"能不能把工具、状态、权限、评测组织成一个可靠系统"，不是"RAG 切块调得多细"。τ²-bench 和 BFCL 用来证明前者，RAG 只作为工具级证据。**

---

## 9. 当前进度（2026-10-27）

- [x] 选定 τ²-bench 为主基准、BFCL 为辅；
- [x] 创建 Python 3.12 conda 环境 `tau2`，`pip install -e .` 成功；
- [x] 5 条 initial smoke：2 条完成（reward 1.0），3 条因 NL judge 缺 OpenAI key / 超时未完成；
- [x] 写 `run_tau2_deepseek_judge.py`，把 NL assertion judge 从 OpenAI `gpt-5.4-mini` 替换为 `deepseek/deepseek-chat`（**非官方评分口径**）；
- [x] **20 条 retail 抽样完成**：
  - **Pass^1 0.90（18/20）**，平均 reward 0.90；
  - DB Match **19/20**；
  - Read Actions **100/110（90.9%）**；
  - Write Actions **22/23（95.7%）**；
  - Infra Error **0**；
  - 失败 2 条：task 3 NL assertion 未满足；task 5 DB state 不匹配；
- [x] BFCL v4 抽样 200 条完成（100 simple_python + 100 irrelevance）：
  - 函数选择 **100/100**；
  - 参数 exact **89/100**；
  - 无关工具不调用 **80/100**（20 条误调用）；
  - 调用错误 **0**；
- [ ] 用公开基准结果更新简历和 2 分钟稿。

> 最终样本口径：τ²-bench retail **20 条抽样，Pass^1 0.90**；NL judge 用 DeepSeek 替代，不是官方 OpenAI judge，不能称为官方榜单成绩。BFCL **200 条抽样**（简化评分）。
> 成本暂不可用：LiteLLM 价格表未映射 `deepseek-flash`，所以 `agent_cost` 为 None。
