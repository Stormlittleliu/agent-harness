# 叙事材料（冻结版）

> 对应 [项目边界与冻结](../design/scope-freeze-2026-11-05.md)。三份材料分工不同，不要混着讲。

## 阅读顺序

1. **[A · 项目演进](A-project-evolution.md)**：先建立整体叙事——RAG → Agent → Harness → 评测 → spec/低代码，以及 5 层结构和与其它项目的区别。
2. **[B · 优化案例](B-optimization-cases.md)**：再用两个有数据的案例证明“会定位、会改、会留边界”。
3. **[C · 现场编辑剧本](C-live-edit-script.md)**：最后用 8–10 分钟 demo 证明“结构是数据，不是代码”。

## 一句话版本

- A：**带评测、结构可编辑的单机 Agent Harness；模型负责决策，框架负责约束和证据。**
- B：**先分层归因，再只改一层；用隔离实验证明改动有效，同时说清没证明的部分。**
- C：**现场只动 spec，不动代码；branch 多路 + default 兜底，保存发布后直接对话。**

## 不同场合怎么用

| 场合 | 用哪份 | 时长 |
|---|---|---|
| 电话/自我介绍 | A 第 1、7 节 | 30–60s |
| 技术面 | A 第 2–4 节 + B 一个案例 | 5–10min |
| 项目深挖 | A 第 3–5 节 + B 两个案例 | 15–20min |
| 现场 demo | C 全文 | 8–10min |

## 统一口径

数字只认冻结文档：408 tests、selfbuilt 26/26（1-trial）、clothing 6/6、retail 5/5、workspace 5/5、planning 12/12、outcome 12/12、BFCL fixture 32/40、catalog 11/132、835 chunks。

不要讲：生产级、多 Agent 平台、官方榜单、真实用户、300 条全量、26/26 稳定性。
