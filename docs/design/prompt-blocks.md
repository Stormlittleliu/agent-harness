# 系统提示词：分块维护，运行时拼接

> 落地日期：2026-11-04。代码：`core/prompts/`；数据：`data/specs/<name>/prompt.yml`。
> 思路来自 `learn-claude-code/s10_system_prompt`：**prompt 是组装出来的，不是写死的。**

---

## 1. 为什么拆

一整段 system prompt 里混着身份、工具规则、引用规则、语气和安全边界，三个后果：

1. 换场景要整段重写，不知道哪句能留；
2. 改一条可能和另一条冲突，而且看不出冲突；
3. 每次请求都带全部内容，用不到的段落也在烧 token。

拆成块之后：**块是数据、顺序是数据、是否加载取决于真实状态**。

## 2. 三个组成部分

| 层 | 文件 | 作用 |
|---|---|---|
| 块 | `data/specs/<name>/prompt.yml` | 每块一个主题（`identity` / `p01`… / `收尾`），可单独改 |
| 引用 | spec 里的 `prompt: {blocks: [...], overrides: {...}}` | 决定拼哪些、按什么顺序；`overrides` 让**这个场景**覆盖某块内容而不改共享块 |
| 拼接 | `core/prompts/assemble.py` | 按顺序 + 条件判断 + `{var}` 插值 + 缓存 |

块可以带 `when`，由**真实状态**决定是否加载，不是从消息里搜关键词：

```
when: always / has_tools / no_tools / has_workflow / no_workflow
      kind:router / kind:agent / has_memory / has_cases
```

块里可以插值 `{name} {kind} {tools} {tool_count} {workflows} {workspace} {memory} {today}`，
例如工具清单变化时不需要改 prompt 文本。

## 3. 拼接流程

```
spec.prompt.blocks ──┐
                     ├─► load_book(prompt.yml) ──► assemble(order, context, overrides)
PromptContext ───────┘                                 │
  name / kind / tools / workflows / has_cases          ├─► text（写回 Scenario.system_prompt）
  workspace / memory / today                           └─► sections（用了哪些块，界面可见）
```

- **先建 Scenario 再拼**：`{tools}`、`{workflows}` 是真实状态，得等场景建好才知道；
- **缓存**：`get_assembled` 用「块内容 + 上下文」的稳定 JSON 做 key，同一份状态只拼一次
  （省的是字符串处理，不是 prompt cache——那是模型侧的事）；
- **失败要响**：spec 声明了 blocks 但 `prompt.yml` 缺块 → 构建直接报错，不会静默给出空 prompt。

## 4. 界面

「🎛 场景编辑」的基本信息里有「提示词分块」面板：

- 列出块（顺序、标题、字数、是否被覆盖）；
- 选中一块可以改内容，保存后写进**这个场景的 `overrides`**（不改 `prompt.yml`，不影响别的场景）；
- 下方直接显示拼接结果，改完立刻能看到全文。

## 5. 迁移方式（已完成的 8 个场景）

`robot_vacuum` 暂时保留 `config/prompts.yml` + `ReportPromptSwitchMiddleware`（报告意图会整段
换 prompt，属于另一套机制），其余 8 个场景按原来的「身份 / 每条规则 / 收尾」机械拆块，
拼接后**去掉空白字符与原文完全一致**，所以用例通过率不变（抽查 `router` 4/4、`general` 4/4）。

要继续拆 `robot_vacuum`，把 `prompts.yml` 的两套文本各拆成一份 book，由中间件按意图选 book 即可。

## 6. 还没做

- **按轮动态拼接**：现在是构建时拼一次；要做到「记忆/日期每轮变」，需要给 `Scenario` 加
  `prompt_provider`，在 `FrameworkAgent` 每次 invoke 前重拼（缓存已就绪，只差接线）；
- **共享块库**：目前块是每场景一份；下一步可以把「安全边界」「引用规则」抽成跨场景共享块，
  用 `when` 决定加载，减少重复文本。
