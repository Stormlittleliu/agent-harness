# 控制台里的场景编辑器

> 落地日期：2026-11-04。代码：`core/interfaces/dashboard/editor.py` +
> `core/scenarios/spec_edit.py` + `core/scenarios/generic.py`。
> 视图名「🎛 场景编辑」，控制台里直接可用。

---

## 1. 它解决什么

没有它的时候，加一个场景要写 `core/scenarios/<name>/scenario.py`；
有了 spec 层之后，这个文件可以只是三行（读 spec → 构建），但**写 spec 仍然要手改 JSON**。
编辑器把"手改 JSON"换成表单 + 校验 + 编译预览，让"场景即数据"这件事真的能演示。

判据只有一条：**不改代码，能不能在界面上加一个场景并且它真的能跑。**

## 2. 数据流

```
表单/表格          draft (dict, 会话内)                    磁盘
────────         ─────────────────────                   ───────────────────────────
基本信息  ──┐                                               data/specs/<name>/vN.json
节点/参数 ──┼──▶  draft ──spec_from_draft──▶ ScenarioSpec ──▶ （校验 + 编译通过才写）
边       ──┤                    │                          data/specs/<name>/active.json
策略覆盖 ──┘                    └──build_workflows(stub)──▶ 预览 DOT（不落盘）
```

- **draft** 就是 `spec_to_dict(spec)` 的形状，所以"载入已有 spec"和"新建"走同一条路径；
- **保存** = `draft_errors()`（结构 + 必填）→ `build_workflows()`（真编译一遍）→ `save_spec()`（原子写 vN + 移动 active）；
- **编译不过不写盘**：错误直接显示在预览区，磁盘上不会留下半成品版本；
- 保存后 `load_agent` / `_graphs` 缓存被清掉，刷新页面就能用新版本。

## 3. 边界（刻意的）

| 能 | 不能 |
|---|---|
| 增删工作流与节点，改边 | 写代码、内联表达式、自定义 Python |
| 引用已注册的块，参数按 `ParamSpec` 渲染 | 引用工具池之外的工具 |
| 显式开关中间件策略（关闭必须写理由） | 改中间件实现、改执行顺序 |
| 保存新版本、载入历史版本、下载 JSON | 自动重连（删节点后悬空边就是错误） |
| 单向 `eject` 转代码 | 从 code 回到 spec |

拖动式画布没做，理由和低代码文档里写的一样：**连线不是难点，难点是"连线之后运行时策略和评测还成立"**。
先把"受约束的表单 + 编译期校验 + 归属守卫"做扎实，画布只是换一层皮。

## 4. 两种场景来源

1. **已有 spec 场景**（目前是 `flow_demo`）：编辑器直接改它的 `data/specs/flow_demo/v*.json`；
2. **界面新建**：只在 `data/specs/<name>/` 下写 spec，构建走
   `core/scenarios/generic.py` 的通用构建器——工具来自固定池（笔记检索 / 读写 / 记忆 / 翻译 / 总结），
   所以"新建 → 保存 → 立刻能在子场景下拉框里选中并跑"是真的，不需要再写 `scenario.py`。
   要别的工具就先 eject 再写代码，这是刻意留的边界，避免 spec 长成第二套工具注册表。

`core/scenarios/registry.py` 的 `list_scenarios()` 会把两类场景并起来：
手写构建器优先，其余按 `data/specs/*/active.json` 动态发现（已 eject 的不算）。

## 5. 和归属守卫的关系

编辑器**自己不做归属判断**，它读 `ownership.status()`：

- `owner=code` → 整页只读，显示历史 spec 与"改代码"的提示；
- `owner=spec` 但 `hash_match=false` → 报错，要求先 `eject`；
- 可编辑 → 正常渲染。

所以"界面能改"和"构建时认谁"是同一个状态机，不是两套开关。
`eject` 按钮带三重确认（写原因 + 勾选 + 已存在代码目录）：没有代码目录的纯 spec 场景不允许 eject，
否则它会从场景列表里消失。

## 6. 演示脚本（90 秒）

1. 选中 `flow_demo`，指出中间件链和「复核 · verify」节点；
2. 把 `answer` 节点的 `prompt` 改一句，加一个 `summarize` 节点，连两条边；
3. 点「只校验」→ 故意留一个悬空边，看到红字报错（这一步是在证明校验是真的）；
4. 补上边，点「保存为新版本」→ 出现 v2；
5. 去「任务执行」跑一句问题，调用链上每一步都标着它属于哪个节点。

第 3 步是重点：**能拦住错误，比能连线更值钱。**
