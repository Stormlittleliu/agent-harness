# 中间件：约束式编排（不是拖拽）

> 重构日期：2026-11-03。装配逻辑从 `framework.py` 的 if 链搬到 `core/agent/pipeline.py`。
> 目标：顺序可保证、策略可配置、删层可审计。

---

## 1. 为什么不是"让用户拖"

中间件顺序有语义，拖错就静默坏掉：

- 权限在最外，被 deny 的工具不该进入审批/超时/重试；
- 审批在超时之外，人思考的时间不能算工具耗时；
- `ToolError` 在 `ToolRetry` 外层，重试耗尽后才转成 error ToolMessage；
- planning 在 todo 之前，先决定是否委派，再进入 todo 流程。

所以顺序**不能开放**，只能由框架保证；开放的是"装哪些、参数是什么"。

## 2. 三个概念

| 概念 | 作用 |
|---|---|
| `SLOTS` | 每个策略固定 slot，越小越靠外；同 slot 内保持声明顺序 |
| `INVARIANTS` | 语义约束，编译期校验，违反直接抛 `PipelineError` |
| `PolicySpec` | 覆盖项：`name / enabled / args / reason` |

slot 表：

```text
permission 0 · custom 10 · hooks 20 · planning 30 · todo 40 · summarization 50
pii 60 · hitl 70 · timeout 80 · error 90 · retry 100 · limit 110 · budget 120
fallback 130 · model_retry 140
```

不变量：

```text
permission < hitl / timeout
hitl < timeout
error < retry
planning < todo
```

## 3. 默认值 + 显式移除

`default_policies(scenario)` 从 `Scenario` 现有字段推导默认列表，所以 8 个代码场景的行为与重构前**逐层一致**（有基线测试守着）。

`policies` 是叠加在上面的覆盖层：

```json
"policies": [
  {"name": "summarization", "enabled": false, "reason": "单轮演示不需要压缩"},
  {"name": "limit", "args": {"run_limit": 12}}
]
```

规则：

- **默认开启**——避免新场景漏掉守卫；
- **移除必须写 `reason`**——让"少了一层"出现在 diff 里，而不是悄悄消失；
- 可以新增默认里没有的策略（例如给没配 `token_budget` 的场景加 `budget`）。

## 4. 等价性怎么保证

重构前先跑一遍全部场景，记录 `[type(m).__name__ for m in agent.middleware]` 作为基线；
重构后 `tests/test_pipeline.py` 逐场景比对，并额外断言 `FrameworkAgent` 实际用的就是 `build_pipeline` 的结果。

改中间件顺序、加策略、改 slot —— 只要基线变了，测试立刻失败。

## 5. 现在的统一口径

```text
所有场景（代码 / spec）→ Scenario → build_pipeline() → create_agent(middleware=...)
```

- 旧装配 if 链已删除，只剩 `default_policies()` 一个推导函数；
- 代码场景用字段声明默认值，spec 场景用 `policies` 覆盖；
- `policies` 目前不是必填——迁移是渐进的，不是一次重写。

**没有把 8 个场景全部改写成字面量 policies 的理由**：那只是把同一份信息抄两遍，
默认值仍要从字段推导；真正的收益（顺序保证、可校验、可审计）已经拿到了。
