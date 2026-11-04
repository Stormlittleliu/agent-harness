# AGENTS.md

给所有编码 Agent（Claude Code / Codex / Cursor / Copilot 等）的仓库契约。改代码前先读这一页。

## 环境

- Python 用 conda 环境 **`langchain`**；裸 `python` 是 3.8，跑不了测试。
- 测试：`python -m pytest -q`（当前 223 passed）。

## 场景归属（硬约束）

部分场景由 spec 驱动，归属写在 `data/specs/<name>/state.json`：

| owner | 含义 | 允许的操作 |
|---|---|---|
| `spec` | `data/specs/<name>/v*.json` 是权威 | 改 spec；**不要改 `core/scenarios/<name>/` 下的代码** |
| `code` | 代码是唯一来源 | 改代码；spec 已失效，不要再指望它生效 |

**改场景代码前，必须先 eject：**

```powershell
python -m core.scenarios.eject <name> --reason "为什么转代码"
```

不 eject 就改代码 → 构建时抛 `OwnershipError`，**不是警告**。这是故意的：
让"忘了同步"变成"跑不起来"，而不是"可视化悄悄过期"。

查看当前状态：

```powershell
python -m core.scenarios.eject <name> --status
```

输出里的 `editable` 告诉你还能不能低代码编辑；`next_action` 告诉你下一步该跑什么。

## 为什么 eject 之后可视化还能同步

因为 code 模式下可视化**不读 spec**，读的是 `compiled_graph.get_graph()`。
结构只有一份来源，就没有需要同步的副本。你不需要"更新可视化"——你只需要 eject。

## 不要做

- ❌ 手改 `data/specs/<name>/state.json` 来绕过守卫；
- ❌ eject 之后继续改 `data/specs/<name>/*.json` 并期望生效（已失效）；
- ❌ 为了通过构建而删除或注释掉 `ensure_spec_editable`；
- ❌ 在 spec-owned 场景里引用未注册的块（会被 `validate_spec` 拒绝）。

## 契约在哪

- `core/agent/pipeline.py` — 中间件策略编排（slot + 顺序不变量 + `policies` 覆盖）；**策略的中文名 / 说明 / 分层写在 `POLICY_DOCS`**，UI 直接读它，别在别处再抄一份；
- `core/quality/selfbuilt.py` — 自建跨分类任务集评测（检索 / 单轮 / 多轮），任务在 `data/evals/datasets/selfbuilt/tasks.jsonl`；
- `core/scenarios/spec.py` — spec schema、校验、编译、版本化读写；
- `core/scenarios/spec_nodes.py` — 块库、`ParamSpec` 参数契约、块的中文名与说明（`label` / `desc`）；
- `core/scenarios/spec_edit.py` — 编辑器背后的纯逻辑（草稿 ↔ spec、加删节点、校验、存版本）；
- `core/scenarios/generic.py` — 通用 spec 场景：`data/specs/<name>/` + 固定工具池就能构建，不写代码；
- `core/scenarios/node_docs.py` — 节点说明注册表（调用链 / 轨迹页用它回答"这一步是哪个节点"）；
- `core/scenarios/ownership.py` — 归属状态机（唯一写 state 的地方）；
- `core/scenarios/eject.py` — 归属 CLI；
- `core/observability/tracer.py` — 本地 trace；每条模型/工具事件带 `node`（LangGraph 节点名）；
- `core/interfaces/dashboard/editor.py` — 控制台的「🎛 场景编辑」视图；
- [docs/design/middleware-pipeline.md](docs/design/middleware-pipeline.md) — 中间件为什么这么排；
- [docs/design/visual-scenario-roundtrip.md](docs/design/visual-scenario-roundtrip.md) — 设计说明与演示脚本；
- [docs/design/scenario-editor.md](docs/design/scenario-editor.md) — 控制台里那个编辑器的边界与数据流。

## 新增工作流节点时

**必须同时写中文说明**，否则 `tests/test_node_docs.py` 会红：代码场景写在
`core/scenarios/<name>/graph.py` 的 `NODE_DOCS`，spec 场景来自块的 `label` / `desc`。
不写说明的节点在调用链上只能显示英文 id，等于没解释。
