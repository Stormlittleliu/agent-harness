# 节点端口契约：参数之外，再说清"吃什么、吐什么"

> 对应 `core/scenarios/spec_nodes.py` 的 `PortSpec` / `block_ports` 与
> `core/scenarios/spec.py` 的 `validate_port_flow`。P0-3。

## 1. 为什么参数不够

`ParamSpec` 只回答"这个块能配什么"：工具名、条数、保存位置。它不回答
"这个块读 state 的哪个槽位、写哪个槽位"。所以以前只能在运行到一半时才发现
"引用校验节点拿不到 answer"，或者"分支节点检查的字段上游根本没产出"。

端口层把这件事提前到校验期：

```text
params  = 配置面（tool / limit / save_to / prompt …）
ports   = 数据面（input / tool_result / answer / scratch.<key>）
```

两层分开还有一个直接原因：很多端口**随参数变化**。`call_tool` 写 answer 还是
`scratch.records`，由 `save_to` 决定；把端口写死在块声明里必然说错。

## 2. 数据模型

```python
PortSpec(name, type, required=False, default=None, help="")
```

- `name`：state 槽位，只允许 `input` / `tool_result` / `answer` / `scratch.<key>`；
- `type`：粗粒度业务类型，见下表；
- `required`：输入端口表示"缺了就是结构错误"；输出端口表示"这个槽位一定有值"；
- `default`：给编辑器/未来默认值用，校验不依赖它。

| 类型 | 含义 | 别名 |
|---|---|---|
| `text` | 字符串、材料、回答 | `str` / `string` |
| `number` | 整数或浮点 | `int` / `float` |
| `boolean` | 布尔 | `bool` |
| `json` | 对象/字典 | `dict` / `object` |
| `any` | 未知或故意不约束 | `*` |

`types_compatible(source, target)`：`any` 双向兼容，其余规范化后必须相同。
返回 `False` 而不是抛异常——校验器要把"哪条边不兼容"当成可展示的错误。

## 3. 动态端口怎么解析

`block_ports(fn, args) -> ResolvedPorts` 在静态声明上叠加参数：

| 来源 | 块 | 作用 |
|---|---|---|
| `save_to` | `call_tool` / `constant` / `llm_text` / `fan_out` | 生成输出端口；默认槽位被覆盖 |
| `queries_from` | `fan_out` | 生成必填输入端口 |
| `field` | `branch` | 生成必填输入端口 |
| `query_key` | `retrieve` | 生成必填输入端口 |
| `{...}` 占位符 | `call_tool.args` / `llm_text.prompt` / `constant.text` / `fan_out.template` | 生成**可选**输入端口 |

占位符端口故意是可选的：`render_template` 遇到缺失 key 会替换成空串，这是块的
既有语义；把它当必填会把"模板里写了个可空字段"误判成结构错误。

`call_tool` 还有一个隐藏输出：工具返回 `docs` 时会把材料写进 `tool_result`。
所以它除了 `save_to` 目标，还声明一个可选的 `tool_result` 输出。

## 4. 静态数据流校验

`validate_spec` → `_validate_workflow` → `validate_port_flow`：

1. 种子：`{"input": "text"}`（Scenario 调用时一定有用户问题）；
2. 对每个节点求不动点：`before = 种子 + 所有前驱的 after`，
   `after = before + 本节点输出`；
3. 再逐节点检查输入端口：
   - 槽位不存在且 `required` → `缺少输入 X（块需要，上游节点没有产出）`；
   - 槽位存在但类型不兼容 → `输入 X 需要 text，上游给的是 number`。

循环图也能收敛：状态本来就会从上一轮带进下一轮，所以环上的节点能看到环内
其他节点的输出。这是有意的，不是漏报。

### 没做什么

- **不改执行器**：`build_workflows` 仍然只编译，端口信息不参与运行；
- 不做运行时类型断言：节点之间传的仍是 state，端口是编译期契约；
- 不校验可选输入；不校验 `scratch` 内部结构（`scratch` 仍是自由字典）；
- 不把端口做成画布可拖拽的东西：端口由块 + 参数决定，画布只改拓扑和位置。

## 5. 新增/修改块时

1. 在 `register_node(...)` 里补 `inputs=` / `outputs=`；
2. 如果端口随参数变化，在 `block_ports` 的动态分支里补一条；
3. 跑 `tests/test_spec_ports.py` 和全量测试——所有 active spec 必须仍然零错误；
4. 在块的 `desc` 里写清它读/写哪些槽位，编辑器和调用链页都读这段说明。

一个反例：给 `retrieve` 写死 `inputs=(PortSpec("input", ...),)` 是错的，因为
`query_key` 可以改成 `scratch.question`。静态声明只放不随参数变化的端口。

## 6. 边界

- 端口类型是**业务语义**，不是 Python 类型系统；`json` 只是"对象"，不校验 schema；
- 端口校验是结构校验，不替代行为用例和评测；
- 新增类型要同时改 `PORT_TYPES`、`TYPE_ALIASES`、本文表格和兼容性测试。
