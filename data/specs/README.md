# data/specs：场景的"数据层"

一个目录 = 一个场景。`active.json` 指向当前版本，`state.json` 记归属（`owner` 只能是
`spec` 或 `code`）。**只要这个目录里有 `active.json`，同名场景就由 spec 构建**；
删掉目录即回退到 `core/scenarios/<name>/` 的代码实现。

## 接管现状（2026-11-04）

| 场景 | 状态 | 用例（代码版 → spec 版） |
|---|---|---|
| `flow_demo` | spec | 1/1（原本就是 spec） |
| `coding_demo` | spec | 7/7 → 7/7 |
| `general` | spec | 4/4 → 4/4 |
| `structured_demo` | spec | 5/5 → 5/5 |
| `mcp_demo` | spec | 3/3 → 3/3 |
| `robot_vacuum` | spec | 13/13 → 13/13 |
| `workspace_assistant` | spec | 5/5 → 5/5 |
| `router` | spec | 4/4 → 4/4 |
| `research_assistant` | spec | 3/3 → 3/3 |

每个场景的 `cases_path` 都指回原来的 `core/scenarios/<name>/cases.jsonl`，
所以代码版和 spec 版跑的是同一批用例，不存在"换了把尺子"。

## 仿造时的取舍（差异都记在这里，不藏在代码里）

- **条件边还没进 spec**：`robot_vacuum` 的"拒答直接结束"、`workspace_assistant` 的
  `refuse` 分支，在 spec 版里都退化成"继续往下走"。答案内容不受影响，只是多跑一个节点。
- **`robot_vacuum.rag_qa.verify`**：原实现用检索到的 docs 做事实核查；spec 版的
  `call_tool` 会把工具返回值里的 `docs` 顺带存进 `tool_result`，所以核查材料仍然是 docs。
- **`workspace_assistant.cite`**：原实现会在缺引用时**补**来源列表；spec 版只做
  `require_citation` 校验，不补。
- **`workspace_assistant.cross_lingual`**：原文按问题里有没有中文字符判断语言；spec 版
  在提示词里写死"用用户提问的语言回答"。
- **`research_assistant`**：`cite` 节点省略（不追加来源 id）；`fan_out` 用 `subagent`
  并发，指令模板与原实现一致。
- **`router`**：无差异——工具、确定性规则、系统提示词都由 `data/routes/router.json` 生成。

## 改场景的正确姿势

- 想改结构 / 提示词 / 工具白名单 / 预算：改这里的 `vN.json`（控制台「场景编辑」就是干这个的）；
- 想改"这个场景还能做什么"（新工具、新中间件、特殊运行时）：改代码，然后
  `python -m core.scenarios.eject <name> --reason "..."` 把它永久转成 code-owned。
