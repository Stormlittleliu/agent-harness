# 资源目录（Resource Catalog）

> 状态：已实现（`core/resources/` + `core/mcp/resource_server.py`）
>
> 一句话：给 Agent 编辑一个**统一、语义一致、只读**的素材对象访问接口，
> 再通过本地 MCP server 暴露成 4 个工具。

## 1. 为什么需要这一层

Agent 编辑场景时要先回答三类问题：

1. 有哪些可用的**工具**？参数 schema 是什么？
2. 某个场景里有哪些**工作流**？节点、边、用到的工具是什么？
3. 有哪些**场景**和**工作流块**？中文名、说明、是否可编辑？

这些信息原本分散在工具池、`data/specs/*/active.json`、场景库和
`spec_nodes` 注册表里，各自的数据形状不同。资源目录只做一件事：
把它们统一成同一种 `ResourceDescriptor`，让调用方不用关心来源。

边界（刻意的）：

- **只读**：不写 spec、不建场景、不改块注册表；
- **不初始化重资源**：不构建 RAG / 向量库 / 子 Agent，不连外部 MCP server；
- **不伪装成向量检索**：搜索是词法打分，返回命中原因，不输出 embedding 分数。

## 2. 统一资源模型

| kind | 含义 | id 形状 | URI 示例 |
|:---|:---|:---|:---|
| `tool` | Agent 可调用的工具 | 工具名 | `ah://tool/search_notes` |
| `workflow` | spec 场景里的工作流 | `<scenario>/<workflow>` | `ah://workflow/flow_demo/qa` |
| `scenario` | 场景库中的场景 | 场景名 | `ah://scenario/clothing_service` |
| `block` | spec 工作流块（节点函数） | 块名 | `ah://block/retrieve` |

URI 规范：`ah://<kind>/<id>`。workflow 多一层场景名，因为同名工作流
（例如 `qa`）可以出现在多个场景里；把场景名放进 URI 后才是全局唯一的。

解析 / 构造 / 校验都在 `core/resources/contracts.py`：

```python
from core.resources.contracts import parse_uri, build_uri, ResourceRef

ref = parse_uri("ah://workflow/flow_demo/qa")  # ResourceRef(kind=workflow, id="flow_demo/qa")
build_uri(ref.kind, ref.id)                    # "ah://workflow/flow_demo/qa"
ResourceRef.from_parts("tool", "search_notes") # 构造
```

非法 URI（协议不对、未知 kind、workflow 少一层/多一层、其他 kind 带 `/`、
带 query/fragment、空段、`..`）一律抛 `ResourceURIError`（`ValueError` 子类）。
URI 合法但目录里没有，抛 `ResourceNotFoundError`。

### ResourceDescriptor

```json
{
  "uri": "ah://tool/search_notes",
  "kind": "tool",
  "id": "search_notes",
  "name": "search_notes",
  "label": "search_notes",
  "description": "按关键词搜索笔记……",
  "tags": ["办公", "笔记", "检索", "搜索", "notes"],
  "source": "core.scenarios.workspace_assistant.tools",
  "version": null,
  "metadata": {"pools": ["office", "workspace_assistant"], "schema_available": true},
  "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
}
```

- `input_schema`：工具是 args JSON schema，块是参数契约，workflow 是输入
  `{input: string}`；没有 schema 时统一返回空 object schema；
- `metadata`：kind 专属信息（工具的所属工具池、工作流的节点/边、场景的
  owner/editable、块的输入输出端口）；
- `version`：场景 / workflow 取 `active.json` 指向的版本号；工具 / 块为 `null`；
- 所有字段都可 JSON 序列化；`to_dict()` 是唯一出口。

## 3. providers：四类来源

代码在 `core/resources/providers.py`，每种 kind 一个 provider。

### 工具（`ToolProvider`）

- 直接从工具模块拿 LangChain tool 对象，读取 `name` / `description` /
  `args_schema.model_json_schema()`；
- 对需要 store 的工具（笔记、任务、研究资料）传一个**占位依赖**：构造工具
  只闭包引用 store，不调用其方法，所以不会建目录、不会写 SQLite；
- RAG 工具、subagent、`route_to_*` 的 schema 写在静态表里：它们的构造函数
  会初始化 embedding / import FrameworkAgent / 加载目标场景注册表；
- 外部 MCP 工具只登记为“未解析占位”（`metadata.external=true`、
  `metadata.resolved=false`），**不启动 server**；
- spec 里引用了但目录没有的工具名也会登记占位，保证覆盖；
- provider 会缓存工具记录，`refresh()` 可清缓存（测试 / 开发用）。

### spec 工作流（`WorkflowProvider`）

- 只读扫描 `data/specs/*/active.json` 指向的 `vN.json`，不 import spec 编译器；
- 每个 workflow 产出一条 descriptor，`metadata.nodes` 保留节点顺序、
  `metadata.edges` 保留边顺序（编辑时可直接对照）；
- 节点 label / desc 来自块库，`metadata.tools` 汇总节点实际引用的工具名；
- 坏的单个 spec 跳过，不影响目录其它部分。

### 场景（`ScenarioProvider`）

- 来源是 `core.scenarios.library.entries()`，不另造一张静态表；
- tags / metadata 暴露 `owner`、`editable`、`from_spec`、`has_workflow`、
  `cases`、`pool`、示例任务等；
- 这是界面“有哪些场景”的同一来源，避免目录和页面各说各话。

### 块（`BlockProvider`）

- 来源是 `core.scenarios.spec_nodes` 的块注册表；
- `input_schema` 由 `ParamSpec` 生成（string/integer/number/boolean/enum/array，
  含 description、default、minimum/maximum、required）；
- `metadata.inputs` / `metadata.outputs` 是解析后的端口，编辑时用于连线校验。

## 4. catalog：list / get / search / kinds

```python
from core.resources.catalog import ResourceCatalog

catalog = ResourceCatalog()
catalog.kinds()                                  # 四类资源及数量
catalog.list(kind="tool", query="笔记", limit=50) # descriptor 列表（无分数）
catalog.get("ah://workflow/flow_demo/qa")        # 单个 descriptor
catalog.search("服装 检索", kind=None, limit=20) # 带 score / 命中原因
```

- `list(kind=None, query=None, limit=200)`：按 kind 顺序 + URI 稳定排序；
  `query` 只做词法过滤，不返回分数；
- `get(uri)`：非法 URI / 不存在抛异常；
- `search(query, kind=None, limit=20)`：每条结果是 descriptor + `score`、
  `match_reasons`（列表）、`match_reason`（拼好的字符串）、`matched_terms`；
- `kinds()`：`kind` / `label` / `description` / `count`；
- `limit` 会被夹到 `1..200`。

### 搜索边界

这是**词法搜索**，不是向量检索：

- 字段：`name`、`label`、`description`、`tags`，权重依次约为 4 / 4 / 1.5 / 2.5；
- 中文：优先 `jieba.lcut`；jieba 不可用时退化为“整段 + 二元组”，仍能命中
  “服装 / 检索”这类词；
- 英文：按 `[a-z0-9_]+` 切词，大小写不敏感；
- 额外加“整体短语命中名称/显示名”的奖励；
- 排序固定为 `(-score, kind 顺序, uri)`，同一 query 重复调用结果一致；
- `score` 只在同一 query 内可比较，不应跨 query 当作绝对相关度；
- 不读取 embedding、不调用模型、不访问网络。

因此：中文搜“服装”能找到 `clothing_service` / `clothing_retrieve`；
搜“检索”能找到 `retrieve` 块、RAG 工具和检索类工作流。找不到时应明确说
“目录里没有”，而不是假装语义检索命中。

## 5. MCP server

启动：

```bash
python -m core.mcp.resource_server
```

`core/mcp/resource_server.py` 用 FastMCP 暴露 4 个工具：

| 工具 | 参数 | 返回 |
|:---|:---|:---|
| `resource_kinds` | 无 | `{ok, kinds:[{kind,label,description,count}]}` |
| `resource_list` | `kind=""`, `query=""`, `limit=200` | `{ok, kind, query, count, items}` |
| `resource_get` | `uri` | `{ok, resource}` |
| `resource_search` | `query`, `kind=""`, `limit=20` | `{ok, query, kind, count, items}` |

所有工具返回 **JSON 字符串**；异常不抛栈，统一返回：

```json
{"ok": false, "code": "get_failed", "error": "ResourceNotFoundError: ..."}
```

客户端直接复用现有同步包装：

```python
from core.mcp.client import resource_connection, load_resource_tools

resource_connection()      # {"transport": "stdio", "command": sys.executable, ...}
load_resource_tools()      # [StructuredTool, ...]，失败返回 []
```

`load_default_tools()` 行为不变（仍然只加载 Memory + Fetch）；资源 server
需要显式调用 `load_resource_tools()`。

### 本地客户端配置

仓库根提供 `.mcp.json.example`，复制为 `.mcp.json` 后填入本机的 conda
Python 与仓库路径即可被 Claude Code / Cursor 等支持 `.mcp.json` 的客户端发现：

```json
{
  "mcpServers": {
    "agent-harness-resources": {
      "command": "<conda-env-python>",
      "args": ["-m", "core.mcp.resource_server"],
      "cwd": "<repo-root>",
      "env": {"PYTHONIOENCODING": "utf-8"}
    }
  }
}
```

`.mcp.json` 含机器路径，已加入 `.gitignore`；提交的是 `.mcp.json.example`。
没有 `.mcp.json` 时也可以直接 `python -m core.mcp.resource_server` 用 stdio 启动。

## 6. Agent 编辑怎么用

推荐流程：

1. `resource_kinds()` 了解目录规模；
2. `resource_search("服装 检索")` 找候选，看 `match_reasons` 判断是否相关；
3. `resource_get(uri)` 拿详情：
   - 改 spec 工作流前看 `metadata.nodes/edges/tools`；
   - 给块传参前看 `input_schema` 与 `metadata.inputs/outputs`；
   - 给场景加工具前看目标工具的 `input_schema`；
4. 通过现有编辑工具（`spec_edit` / 编辑器 / 文件工具）落盘；
   **资源目录本身绝不写文件**。

适合 Agent 编辑的读取顺序：先搜索、再 get、最后才修改；不要凭记忆猜工具名
或工作流节点，目录里的 `source` 和 `version` 可以指回权威数据。

## 7. 已知限制

- 外部 MCP 工具没有启动 server，描述/参数是占位，`input_schema` 为空；
- RAG / subagent / route 工具的 schema 是静态登记，若实现签名变化需要同步；
- 没有分页游标；单次最多 200 条；
- 搜索不做同义词/拼音/向量召回，中文分词效果依赖 jieba；
- 工具 provider 有进程内缓存，运行中新增工具需 `refresh()` 或重启 server；
- 这是一个本地只读目录，不是权限系统：调用方仍要遵守场景归属规则
  （改场景代码前先 eject）。
