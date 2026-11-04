# 面试用：代表性案例 + 编辑页搭建剧本

> 用途：面试口述 + 现场 demo。
> 原则：只讲有证据的；数字不是准确率，是诊断矩阵。

## 一、四个代表性案例

### 案例 1：planning policy（岗位 A 主叙事）

**问题**
规划/委派功能存在，但自然语言几乎不触发：`natural 0/10`、`routed 0/10`。

**假设**
不是模型不会，是“没有稳定触发条件”。规则 policy 只在 eligible 子集注入，不命中就 abstain。

**干预**
- 第一次模型调用前按规则判断是否注入 `route_to_*` / `subagent` / `create_task`；
- 不命中、分数不足或平局时 abstain，交回模型；
- trace 记录是否触发、命中哪条规则。

**证据**

```text
router:  baseline 11/12 → policy 12/12
coding:  natural 0/10、routed 0/10
         policy eligible 3/10 → 3/3 触发；7/10 abstain
平均模型调用：1.92 → 1.08
```

复现：

```powershell
python -m core.experiments.planner_eval --trials 1
python -m core.experiments.trigger_rate --variants natural,routed,policy
```

**取舍**
只覆盖规则能判的 eligible 子集，不是自主 planner；abstain 是设计的一部分，不是失败。

**一句话**
> 功能存在 ≠ 功能会被触发；先测 trigger rate，再谈能力。

**60 秒口述**
> 我曾经加过 plan/subagent，但发现自然语言下 10 条任务一次都没触发。后来不是换更聪明的模型，而是加了一层确定性 planning policy：只在规则能判的 eligible 子集注入工具调用，其余 abstain。结果 eligible 从 0/10 变成 3/3 触发，router 从 11/12 到 12/12，平均模型调用从 1.92 降到 1.08。这个案例说明，Agent 的问题经常不是“不会做”，而是“没有被稳定触发”。

---

### 案例 2：任务级夹具 / missing（岗位 A/B 都能用）

**问题**
用 `robot_vacuum` 这种业务场景跑所有任务，失败分不清是任务难还是场景不匹配。

**干预**
- 一条任务、一组按任务配的工具、一组断言；
- 五个变体：clean / distractor / missing / failure / permission；
- BFCL 10 条任务 × 4 变体 = 40 条。

**证据**

| variant | 通过 | 说明 |
|---|---:|---|
| clean | 10/10 | 工具适配/prompt/参数 schema 成立 |
| distractor | 10/10 | 3 个同域干扰工具没有被误调 |
| failure | 10/10 | 工具报错后说明失败，不假装成功 |
| missing | 2/10 | 没工具时 8 条直接心算，不说“工具不可用” |

复现：

```powershell
python -m core.quality.fixtures --family bfcl --limit 10
```

**取舍**
stub 是模拟，10 条是小样本，不是官方 BFCL 分数。

**一句话**
> 总分只能告诉你挂了，变体能告诉你挂在哪。

**60 秒口述**
> 我把评测从“业务场景套任务”改成“按任务配工具”。BFCL 10 条任务跑了 40 条，clean、distractor、failure 都是 10/10，说明工具适配和选择没问题；missing 只有 2/10，8 条在没有工具时直接心算，不说明“工具不可用”。这个矩阵比 32/40 这个总分有用，因为它直接指出要修的是边界行为，不是再加一个工具。

---

### 案例 3：selfbuilt 耦合 → 迁移（岗位 B 主叙事）

**问题**
`selfbuilt` 26 条里 18 条复用 `robot_vacuum`。跑的是产品的完整 prompt、意图路由和 13 条业务 case，测的是“任务能不能塞进场景”。

**干预**
- 新增 `TaskFixture`，按任务配工具；
- 先迁 `robot_vacuum` 的 8 条单轮/多轮；
- 迁移时发现 `sb-single-008` 只写了 `fetch_external_data`，但“这个月”需要 `get_current_month`，已补任务定义。

**证据**

```text
迁移：8/8
产品 prompt / 意图路由 / 13 条业务 case：不再参与
```

复现：

```powershell
python -m core.quality.fixtures --family selfbuilt --limit 8
```

**取舍**
10 条 retrieval 留在能力层；research/coding/router/workspace 的任务定义还不完整，没硬迁。

**一句话**
> 评测复用产品场景，测的是场景，不是任务；任务定义缺口不能伪装成模型失败。

**60 秒口述**
> 我一开始图省事，`selfbuilt` 直接复用 `robot_vacuum`。后来发现 26 条里 18 条跑的是产品 prompt 和 13 条业务 case，这样测出来的失败没有归因。后来我把 8 条单轮/多轮迁到任务夹具，8/8；迁移时还发现任务定义少了一个前置工具 `get_current_month`，模型只能追问。这不是模型失败，是任务定义缺口，我把它修了。

---

### 案例 4：permission / HITL（岗位 B 的失败恢复/安全）

**问题**
高风险工具需要审批；拒绝时模型仍然会在 message 里“提议”调用，容易把“提议”当成“执行”。

**干预**
- 真实 `HumanInTheLoopMiddleware`；
- approve：中断 → resume 批准 → 工具执行；
- reject：resume 拒绝 → 工具不执行；
- 判分看 stub 的实际调用，不看 AIMessage 的 `tool_calls`。

**证据**

```text
permission_approve: 1/1
permission_reject: 1/1
reject 时 stub 无调用记录，回答说明未执行
```

复现：

```powershell
python -m core.quality.fixtures --family permission
```

**取舍**
只覆盖 `reset_device`，没有远程策略、多工具组合、权限继承。

**一句话**
> trace 里的 tool_call ≠ 副作用；安全评测要看“有没有真的执行”。

---

### 备选：负结果（被问到“失败/取舍”时用）

- `arg validation`：第 5 轮只改 BFCL 校验，RAG 却 +1，属于噪声，没有独立证据；
- `english embedding`：BFCL -1、RAG -1，没有超过 hybrid；
- `prompt routing`：BFCL +3、RAG -2，是 trade-off，不是纯赢。

**一句话**
> 不是每个“看起来合理”的优化都有效；优化要带回归和负结果。

## 二、按岗位分配

| 岗位 | 主叙事 | 第二 | 备选 |
|---|---|---|---|
| A（平台/核心能力） | planning policy | 任务夹具/missing | RAG hybrid + 负结果 |
| B（真实任务/稳定可用） | selfbuilt 耦合→迁移 | missing 2/10 | permission HITL |

## 三、编辑页现场搭建剧本（约 3 分钟）

### 目标

从空场景搭一个“笔记问答”Agent：

```text
START → search（search_notes）→ answer（llm_answer）→ verify（require_citation）→ END
```

不写代码，只在编辑页操作。

### 0:00–0:20 打开

```text
http://127.0.0.1:8501/?app=build
```

点顶部 **构建**，进入 **构建 / 场景库**。

口述：

> 我不写代码，直接从控制台搭一个场景。这里所有场景都由 spec 接管，结构存 `data/specs/<name>/`，工具来自工具箱。

### 0:20–0:45 新建

1. 滚到页面底部，展开 **新建场景**；
2. 场景名输入 `note_qa_live`；
3. 点 **创建 v1**。

口述：

> 新建会给一个能编译的最小模板：检索 → 生成回答 → 引用校验。默认工具是 `search_notes`。

成功后会自动跳到场景详情。

### 0:45–1:20 看结构

1. 点页签 **结构**；
2. 画布上应看到三个节点：`search`、`answer`、`verify`；
3. 指出边：`START → search → answer → verify → END`。

口述：

> 节点只能引用已注册的块，不能凭空写一个工具；参数按块契约渲染，保存前会编译。

### 1:20–2:00 改配置

1. 点 **编辑方式** 里的 **📝 表单**；
2. **场景描述**：
   ```text
   基于个人笔记的问答；回答必须引用来源
   ```
3. **系统提示词**：
   ```text
   你是笔记问答助手。只根据检索材料回答；每个结论后标注 [来源id]；资料不足就明确说无法确定。
   ```
4. **工具白名单**：保留 `search_notes`；可以再加 `read_note`；
5. 展开 `search` 节点，确认：
   - 工具：`search_notes`
   - limit：`5`
   - query_key：`input`
6. `answer` / `verify` 保持默认。

口述：

> `search` 是确定性检索，`answer` 才是模型生成，`verify` 检查回答里有没有 `[来源id]`。哪些环节用模型、哪些用确定性程序，是在这里定的。

### 2:00–2:25 校验并保存

1. 点 **只校验，不保存** → 看到 **校验通过**；
2. 点 **保存为新版本**。

口述：

> 校验不过不会写盘；保存会生成新版本并设为 active。

### 2:25–2:50 发布

1. 点页签 **发布**；
2. 入口标题：`笔记问答 Demo`；
3. 一句话介绍：`只根据你的笔记回答，并标注来源`；
4. 开场白：
   ```text
   Agent 评测应该关注哪些指标？
   ```
5. 点 **校验并发布**；
6. 点右上角 **对话入口**。

### 2:50–3:10 对话

在对话页问：

```text
Agent 评测应该关注哪些指标？
```

期望：回答带 `[来源id]` 引用；资料不足时说明无法确定。

口述：

> 这个场景从创建到发布没有写一行代码；结构、工具、提示词、发布都是编辑页完成的。

### 兜底

- 如果 `note_qa_live` 已存在：换 `note_qa_live_02`。
- 如果发布校验报“节点没有中文说明”：说明块说明缺失，不要现场修，直接说“这是块库文档问题，我换一个已有场景演示”，改用 `workspace_assistant` 的结构页。
- 如果模型没引用来源：`verify` 会在 `scratch.error` 记一笔，正好用来讲“引用校验是确定性程序，不靠模型自觉”。

### 清理

```powershell
Remove-Item -Recurse -Force data/specs/note_qa_live
Remove-Item -Force data/runtime/spec_drafts/note_qa_live.json -ErrorAction SilentlyContinue
Remove-Item -Force data/runtime/spec_layout/note_qa_live.json -ErrorAction SilentlyContinue
```

## 四、不要讲

- ❌ 32/40 是准确率；
- ❌ 多 Agent 协作已做；
- ❌ MCP 全链路；
- ❌ 真实用户/线上数据；
- ❌ 语音/OCR/多模态/端侧都覆盖；
- ❌ 382 个测试是成果。
