# 兜底检索回答节点：从"只能拒答"到"交回模型"，并当作编辑能力的展示窗口

> 实现：[`core/scenarios/spec_nodes.py`](../../core/scenarios/spec_nodes.py) 的 `fallback_answer`
> 测试：[`tests/test_fallback_node.py`](../../tests/test_fallback_node.py)
> 冻结例外：见 [scope-freeze](../design/scope-freeze-2026-11-05.md) 第 5 节

## 1. 一句话

规则没命中、或者多个领域都命中时，**不再由 spec 预先决定查哪个库**：节点把候选库各查一次，带上库名一起交给模型，由模型判断该信哪份材料、要不要说"查不到"。

## 2. 为什么是"块"，不是"policy"

同一件事有两个落点，职责不同，别混：

| | 中间件 policy（`PlanningPolicy`） | 工作流块（`fallback_answer`） |
|---|---|---|
| 作用对象 | 一个 Agent 的**第一次工具调用** | 一张**图里的某条边** |
| 谁决定 | 代码里的规则表 | spec 里的节点和连线 |
| 能不能在画布上编辑 | 不能，改配置/改代码 | **能，加节点、换连线** |
| 适合演示什么 | 规则可测、可审计 | **结构是数据** |

`retail_router` 这种"固定三分支 + 兜底"的图，缺的正是第二列：兜底那条边现在只能连到一个常量拒答。所以这里做块。

## 3. 节点契约

```python
fallback_answer(state, scenario, tools, limit=4, prompt="", query_key="input")
```

**参数（编辑器据此渲染表单）**

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `tools` | `tool_list` | 必填 | 候选检索工具，按顺序各查一次 |
| `limit` | `int` | 4 | 每个库取几条（1–20） |
| `prompt` | `str` | 空 | 回答指令；留空用默认"先判断属于哪个库" |
| `query_key` | `str` | `input` | 从 state 哪个键取问题 |

**端口（编译器据此校验数据流）**

| 方向 | 槽位 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| 输入 | `input` | text | 是 | 用户问题 |
| 输出 | `answer` | text | 是 | 最终回答 |
| 输出 | `tool_result` | text | 否 | 合并后的材料（可接引用校验） |

**行为**

1. 依次调用 `tools`，材料按 `【工具名】` 分段拼接；
2. 单个库抛异常只记 `scratch.error`，不打断整张图；
3. **全都没有材料 → 直接返回固定拒答，不调用模型**（不让模型凭空编）；
4. 有材料 → 一次模型调用，指令要求"先判断属于哪个库，只用相关材料，不足就说无法确定"；
5. `scratch.fallback_sources` 记录每个库有没有命中，便于事后归因。

**一个容易踩的坑**：RAG 工具签名是 `rag_retrieve(query, k=4)`，不是 `limit`。块里按工具自己的 `args` 适配（有 `k` 传 `k`，有 `limit` 传 `limit`），否则多传一个参数就是 TypeError。

## 4. 它怎么成为"编辑"的展示窗口

### 基线：一条僵化的工作流

`retail_router`（active v1）现在是这样：

```
classify ──robot────→ robot_search ──┐
        ├─clothing─→ clothing_search ─┼→ answer → verify → end
        └─other────→ refuse ──────────┘（常量：只处理这两类）
```

`other` 这条边是死的：只能拒答。

### 演示动作（约 90 秒）

1. 打开「构建 → retail_router」，指着画布说：**"这是一张已经跑起来的工作流，结构在 JSON 里，不在代码里。"**
2. 对话端先问一句不在两个库里的：*"我想给客厅换个灯，怎么选色温？"* → 得到拒答。
3. 回画布：**删掉 `refuse`**，从块库拖入「兜底检索回答」，`tools` 勾上 `robot_retrieve` + `clothing_retrieve`；把 `classify` 的 `other` 边接到它，再接 `verify`。
4. 保存 → 发布 → 再问同一个问题。
5. 收尾：**"刚才没改一行代码，改的是结构；发布之后对话端立刻生效，撤回就回到旧结构。"**

### 如果画布现场出问题

保底方案：直接把这段贴进 spec 的 `workflows.triage.nodes`，等价于画布拖拽的结果。

```json
{
  "id": "fallback",
  "fn": "fallback_answer",
  "args": { "tools": ["robot_retrieve", "clothing_retrieve"], "limit": 4 }
}
```

边：`{"from": "classify", "to": "fallback", "when": "other"}`、`["fallback", "verify"]`。

## 5. 实施步骤

| 步骤 | 状态 | 说明 |
|---|---|---|
| 块实现 + 参数/端口注册 | ✅ | 编辑器调色板从 `block_catalog()` 自动出现，无需改 UI |
| 5 条离线测试 | ✅ | 合并 / 全空拒答 / 单库失败 / 空 tools / 参数契约 |
| 现场编辑（演示动作） | ⬜ | **不预改 active spec**，编辑本身就是要演示的东西 |
| 预置 v2 作为回退 | ⬜ | 可选；若现场画布卡住，直接切 v2 |

## 6. 验收

```powershell
python -m pytest -o addopts="" -q tests/test_fallback_node.py tests/test_scenario_spec.py tests/test_spec_ports.py tests/test_node_docs.py
```

手测三件事：

- 两个库都有材料 → 回答里能看到两份材料的痕迹，`scratch.fallback_sources` 两个 1；
- 两个库都空 → 固定拒答，**模型没被调用**；
- 一个库抛错 → 另一个库照常回答，`scratch.error` 里有失败库名。

## 7. 边界（面试要主动说）

- 这**不是**自主规划：查哪些库仍是 spec 里配死的，只是"信哪份、答不答"交给模型；
- 多库全查有成本：N 个库就是 N 次检索，没有先做库级路由；
- 没有 rerank、没有多模态检索；
- 没跑真实模型评测，**没有 fallback 率/准确率的数字**，只有单测。

## 8. 回退

删块 + 删测试；`retail_router` 的 active 仍是 v1，演示编辑不回写 active，所以回退成本为零。
