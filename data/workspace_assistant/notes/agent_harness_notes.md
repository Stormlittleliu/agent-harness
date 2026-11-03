# Agent Harness 学习笔记

## 评测
- Agent 评测要看 pass^k、任务通过率、失败类型。
- 同时记录 token 成本、p50/p95 时延和平均步数。
- 代码类任务应以 outcome（测试、文件、diff）为准，不能只看退出码。

## 工具
- read / write / edit / glob / grep / run_command 是编码 Agent 的基础工具。
- 工具描述要说明何时使用、何时不要使用，返回结果要可控。

## 记忆
- 短期记忆用 checkpoint，长期偏好用 SQLite 或向量检索。
- 写入记忆要有门槛，召回结果要避免污染当前上下文。
