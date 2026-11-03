# spec 场景：创建 + 可视化编辑（伪低代码，不追求完备转换）

> 定位：给场景层**增加一种受约束的定义方式**——填表/连线生成 spec，保存后即可运行、可再编辑。
> 明确不做：把现有 8 个代码场景序列化、任意图往返、自动重连、拖拽画布。
> 面试：2026-11-06 下午。
>
> **环境**：conda `langchain`（`C:\Users\28980\anaconda3\envs\langchain\python.exe`）。
> 裸 `python` 是 3.8 且没有 pytest，所有命令先 `conda activate langchain`。

---

## 1. 范围（先划死，避免做成半个平台）

| 做 | 不做 |
|---|---|
| 从表单创建一个 **spec 场景**并保存 | 把 `robot_vacuum` 等代码场景转成 spec |
| 编辑 spec 场景的节点/边/开关，保存新版本 | 任意代码图 → spec 的完备转换 |
| 图**从 spec 渲染**，草稿态也能看 | 图必须与 compiled graph 逐节点等价 |
| 保存时编译 + 校验，失败不落盘 | 自动重连悬空边 |
| 保存后跑一条 case 验证 | 拖拽画布、多人协作、发布 |

一句话：**spec 是一种"新增场景的方式"，不是"所有场景的序列化格式"。**

---

## 2. 双来源，一种视图

```text
代码场景（8 个）  →  只读视图（来自 compiled graph，现有 graphviz 不动）
spec 场景（新建） →  可编辑视图（来自 spec，保存后编译运行）
```

UI 上必须标来源 badge：`来源: 代码（只读）` / `来源: spec v3（可编辑）`。

**这条比任何功能都重要**：面试官看到"有些能编、有些不能"，会问为什么——答案就是设计边界：代码图不可完备序列化，所以只读；spec 图天生是数据，所以可编辑。

---

## 3. 数据流

```text
表单/编辑 → draft spec（内存） → 图（直接从 spec 渲） → 校验
   → 编译 StateGraph → 失败则保存失败（原子） → 落盘 data/specs/<name>/v<N>.json
   → 更新 active.json →（可选）跑一次工作流，对比输出
```

关键点：**图从 spec 渲，不从 compiled graph 渲。**否则改到一半编译不过，就没图可看，编辑体验直接崩。

---

## 4. spec 形状（受约束，故意不完整）

```json
{
  "schema_version": 1,
  "scenario": {
    "name": "flow_demo",
    "description": "spec 构建的演示场景",
    "tools": ["search_notes", "read_note", "write_note"],
    "system_prompt": "你是办公助手，回答必须带 [笔记id] 引用。",
    "harness": {"enable_todo": false, "enable_summarization": true, "tool_call_limit": 8}
  },
  "workflows": {
    "qa": {
      "nodes": [
        {"id": "search", "fn": "retrieve", "args": {"tool": "search_notes", "limit": 5}},
        {"id": "answer", "fn": "llm_answer"},
        {"id": "verify", "fn": "require_citation"}
      ],
      "edges": [
        ["START", "search"], ["search", "answer"], ["answer", "verify"], ["verify", "END"]
      ]
    }
  }
}
```

**受约束的地方（就是"伪"的来源，要主动讲）**

- 只有**一个通用 state**：`{"input", "tool_result", "answer", "scratch"}`；节点只能读写这几个键。想要任意 state → 回去写代码。
- 节点只能引用 `NODE_REGISTRY` 里的函数，不允许内联代码。
- 只有线性/简单分支，没有子图、没有动态路由。

---

## 5. 块库（6 个块，每个都带参数契约）

| fn | 作用 | 参数 |
|---|---|---|
| `retrieve` | 调指定工具，结果写 `tool_result` | `tool`(必填), `limit`(1–20), `query_key` |
| `llm_answer` | 用 prompt + tool_result 生成 `answer` | `prompt` |
| `require_citation` | 校验 answer 里有 `[id]`，没有就置 `scratch.error` | `pattern` |
| `summarize` | 确定性截断 tool_result | `max_chars`(100–8000) |
| `write_report` | 把 answer 写文件（outcome 可断言） | `path` |
| `react_loop` | **复合块**：内部一个完整 ReAct 循环（`create_agent`） | `tools`(必填), `prompt`, `max_steps`(1–12), `stop_when` |

参数不是随便塞的 dict，而是 `ParamSpec`：

```python
@register_node("react_loop", params=(
    ParamSpec("prompt", "str", default=""),
    ParamSpec("tools", "tool_list", required=True),
    ParamSpec("max_steps", "int", default=6, minimum=1, maximum=12),
    ParamSpec("stop_when", "enum", default="no_tool_calls",
              choices=("no_tool_calls", "answer_has_citation")),
))
```

编译器按契约校验：未知参数、缺必填、类型错、超范围、枚举越界、`tool_list` 引用了场景里不存在的工具 —— 全部拒绝。
UI 以后直接用 `block_params(name)` 渲染表单，不用手写控件。

**`react_loop` 是原子块**：内部是 `create_agent` 而不是节点，所以不能展开成子图。
要手拼循环，需要条件边 + 工具节点，那是下一层能力（见第 9 节）。

---

## 6. 校验规则

1. `fn` 在 `NODE_REGISTRY` 里；
2. 边两端是已声明节点或 `START`/`END`；
3. 所有节点可达，且存在到 `END` 的路径；
4. **悬空边直接报错，不自动重连**（如删掉 `verify` 后 `answer→verify` 必须手动改成 `answer→END`）；
5. `schema_version` 不匹配拒绝。

保存是原子的：编译失败 → 报错 + 不写盘 + 保留 draft。

---

## 7. 工时（已完成部分）

| 任务 | 状态 |
|---|---|
| `core/scenarios/spec_nodes.py`：6 个块（含 `react_loop`）+ `ParamSpec` 参数契约 | ✅ 已完成 |
| `core/agent/pipeline.py`：中间件 slot 编排 + 不变量 + `policies` 覆盖（[说明](middleware-pipeline.md)） | ✅ 已完成 |
| `core/scenarios/spec.py`：schema + 校验（结构 + 参数 + 策略）+ 编译 + 版本化读写 | ✅ 已完成 |
| `core/scenarios/flow_demo/`：spec 构建的第 9 个场景 | ✅ 已完成 |
| `data/specs/flow_demo/v1.json` + `active.json` | ✅ 已完成 |
| `tests/test_scenario_spec.py`：33 条用例 | ✅ 全过（全套 117 passed） |
| 架构页：创建表单 + 编辑 + 图渲染 + 保存 + 重载 | ⬜ 待做（≈3h） |
| `owner: spec/code` 元数据 + eject + 只读模式 | ⬜ 待做（≈2h） |
| 组（展开/折叠） | ⬜ 待做（≈4h） |
| 条件边 + 手拼 ReAct | ⬜ 面试后（≈5h+） |
| 演示脚本 dry-run | ⬜ 待做（≈1h） |

不改任何现有场景、不改 `FrameworkAgent`——`Scenario.workflow_factory` 已经能接 `{name: compiled}`，集成点现成。

---

## 8. 演示脚本（3 分钟，已实测）

> 关键修正：**删掉的应该是 `search`，不是 `verify`。**删 verify 只是少一道校验，回答照样有引用，看不出差别；
> 删 search 之后模型拿不到材料，直接拒答——差异肉眼可见。

1. 架构页：`robot_vacuum` 显示「来源：代码（只读）」→ "这是代码定义的，只能看"；
2. 切到 `flow_demo`：「来源：spec v1（可编辑）」，图上是 `search → answer → verify`；
3. 删掉 `search`，边改成 `__start__ → answer`（**先故意留一条 `__start__→search` 的悬空边 → 校验立刻报错**，证明守卫工作）→ 改对 → 保存 v2 → 图变 2 节点；
4. 跑：
   ```powershell
   conda activate langchain
   python -m core.interfaces.workflow_cli --scenario flow_demo --run qa --input "根据笔记，Agent 评测应该关注哪些指标？"
   ```
   输出变成拒答，`scratch.error = 回答缺少 [来源] 引用`；
5. 载入 v1 → 同一个命令 → 回答带 `[seed/agent_harness_notes]` 引用。

**实测结果（2026-11-03）**

| 版本 | 输出 | scratch |
|---|---|---|
| v1（含 search） | 引用 `[seed/agent_harness_notes]` 的正常回答 | `error: None` |
| v2（删 search） | "无法确定…没有提供任何笔记内容" | `error: 回答缺少 [来源] 引用` |

**必须说清的边界**：`cases.jsonl` 跑的是 **Agent**（工具 + 提示词），不受图编辑影响；
图编辑影响的是**工作流运行**。所以"删节点后被抓住"靠的是工作流输出 + 节点内校验，
不是 agent 评测报告。别把这两件事混着说。

---

## 9. 归属与同步：契约怎么抵达任意编码 Agent

**核心思路：不靠 agent 自觉，靠构建期强校验。**

| 层 | 载体 | 作用 |
|---|---|---|
| 入口 | `AGENTS.md` / `CLAUDE.md` | 所有主流编码 agent 都会读；写清命令和禁区 |
| 状态 | `data/specs/<name>/state.json` | `owner: spec / code`，唯一写入口是 `ownership.py` |
| 查询 | `python -m core.scenarios.eject <name> --status` | 输出 `editable` / `hash_match` / `next_action`，agent 可解析 |
| 强制 | 构建时 `ensure_spec_editable` | 代码漂移 → 抛 `OwnershipError`，**不是警告** |
| 指令 | 报错文本本身 | 直接给出要跑的那一条命令，agent 照抄即可 |

**为什么"同步可视化"不需要 agent 做事**：code 模式下图从 `compiled.get_graph()` 内省，
不读 spec。结构只有一份来源，就没有需要同步的副本。

**单向门为什么关得死**：eject 之后 `build_scenario()` 不再读 spec，
所以就算手改 `data/specs/<name>/*.json` 也不会生效——不是"建议别改"，是"改了没用"。

**实测（2026-11-03）**

```text
1) 首次构建 → 写入 state.json（owner=spec, hash=8bc5a28…）
2) --status  → editable: true
3) 给 scenario.py 追加一行 → 构建失败：
   OwnershipError: 场景 flow_demo 的代码已被修改，spec 与代码分叉。
   请先运行：python -m core.scenarios.eject flow_demo --reason "说明"
4) 还原文件 → 构建恢复通过
```

---

## 10. 讲法

> "我给场景层加了一种受约束的定义方式：表单生成 spec，spec 直接渲染成图，保存时编译成 LangGraph——编译不过就不落盘。改完跑一次工作流就能看到行为变化，改坏了载入上一版就回来了。
>
> 它不是完备的低代码——只有一个通用 state、节点只能引用注册函数、没有自动重连。因为完备序列化代码图是另一个量级的工作，而且不值得：真正的价值是证明 Scenario 契约可以被外部生成，不是把代码搬进 JSON。"

**别说**："我做了个可视化编排平台。"
