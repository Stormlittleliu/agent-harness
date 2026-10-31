# Runtime：任务图 / 工作区 / 运行窗口

独立的运行时层，不依赖 `core.agent`；场景层通过 `Scenario.runtime` 配置。

## 组件

```text
core/runtime/
├── tasks.py        # SQLite 任务图（状态 / owner / blocked_by）
├── task_tools.py   # create/list/get/claim/complete/fail tools
├── workspace.py    # 安全路径 / read_file / glob / run_command
├── runner.py       # 认领 → 跑 Agent → 完成/失败 → 解锁下游
└── config.py       # RuntimeConfig，供 Scenario 使用
```

## Hooks

Hook 协议和中间件在 `core/agent/hooks.py`；场景通过 `RuntimeConfig.hooks` 注册实现。

事件：

```text
UserPromptSubmit  用户输入进入模型前，可返回新 query
PreToolUse        工具执行前，返回非 None 即拦截
PostToolUse       工具执行后，日志/告警
Stop              一轮 run 结束
TaskStart / TaskComplete / TaskFail
```

场景层直接注册：

```python
RuntimeConfig(hooks={
    "PreToolUse": [permission_hook, log_hook],
    "PostToolUse": [large_output_hook],
    "Stop": [summary_hook],
})
```

Hook 异常只记录日志，不拖垮主流程。

## Subagent

实现放在 `core/agent/subagent.py`，场景通过 `RuntimeConfig.subagent` 配置：

```python
SubagentConfig(
    allowed_tools=["read_file", "glob", "run_command"],
    max_model_calls=12,
    token_budget=20000,
    timeout_seconds=120,
)
```

- 子 Agent 使用全新 context / 独立 thread，不继承父对话；
- 工具白名单 + 排除 `subagent` 自身，禁止递归；
- 有超时、步数、token 预算；
- 只返回最终摘要，中间过程丢弃。

## 任务图

- SQLite 单文件，跨进程/重启保留；
- `pending / in_progress / completed / failed`；
- `blocked_by` 依赖，完成后自动解锁下游；
- Agent 通过 `create_task / list_tasks / claim_task / complete_task / fail_task` 操作；
- `TaskRunner` 也可以从外部认领并执行任务。

## 工作区与运行窗口

- `read_file`：只读工作区内文件，带行号，最多 200 行；
- `glob`：工作区内 glob；
- `run_command`：工作区内执行 shell，危险命令拒绝，输出最多 20k 字符，日志写入 `data/runtime/run_window/`；
- 控制台的 **🖥 运行窗口** 页签展示任务图、任务详情和命令日志，可对 ready 任务点“执行选中任务”。

## 场景示例

`core/scenarios/coding_demo/`：

```text
tools: read_file / glob / run_command + 6 个任务工具
hooks: prompt / pre_tool / post_tool / stop / task_*
workspace: data/runtime/coding_workspace
task db: data/runtime/tasks/coding_demo.sqlite
```

运行：

```bash
python -m core.quality.runner agent --scenario coding_demo
python -m streamlit run app_agent.py   # 场景选 coding_demo
```

## 边界

- 单进程 SQLite，没有分布式锁/多 worker；
- `run_command` 是**进程内 shell**，不是容器沙箱；危险命令只做字符串拒绝；
- 没有后台任务线程池/定时调度；
- 任务图是单机持久化，不是多 Agent 协作协议；
- Hook 只覆盖 prompt / tool / stop / task 事件，不是完整插件系统。
