# LangGraph 工作流

工作流用 YAML 定义，`agent/workflow.py` 负责编译成 LangGraph `StateGraph`。
新增流程不需要改框架代码，只要在 `config/workflows/` 下加一个 YAML。

## 节点类型

| 类型 | 作用 | 关键字段 |
|:---|:---|:---|
| `rag_retrieve` | 检索当前场景知识库 | `output`（默认 `context`） |
| `rag_answer` | 基于 `input` + `context` 生成回答 | `output`（默认 `answer`） |
| `llm` | PromptTemplate + chat_model | `prompt`、`output` |
| `tool` | 调用场景注册工具 | `tool`、`args`、`output` |
| `router` | 按字段关键词分流 | `field`、`routes` |

`args` / `prompt` 中的 `{state_key}` 会用当前 state 替换；`prompt` 使用
`PromptTemplate.from_template`。

## 示例：rag_qa

```yaml
name: rag_qa
entry: retrieve
nodes:
  retrieve:
    type: rag_retrieve
    output: context
    next: generate
  generate:
    type: rag_answer
    output: answer
    next: check_refusal
  check_refusal:
    type: router
    field: answer
    routes:
      - if_contains: ["没有相关信息", "资料不足"]
        target: end
      - default: verify
  verify:
    type: llm
    prompt: "资料：{context}\n回答：{answer}\n只输出有依据或无依据。"
    output: verified
    next: end
```

## 示例：report

```yaml
name: report
entry: get_user_id
nodes:
  get_user_id:
    type: tool
    tool: get_user_id
    output: user_id
    next: get_current_month
  ...
```

## 运行

```bash
python test_entry.py workflow --list
python test_entry.py workflow --run rag_qa --input "小户型适合哪些扫地机器人？"
python test_entry.py workflow --run report --input "生成我的使用报告"
python test_entry.py workflow --run rag_qa --dry-run   # 只编译，不调用模型
```

`--dry-run` 只验证图结构（节点、边、路由目标），不会产生 API 费用。
