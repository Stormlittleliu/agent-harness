# BFCL 坏例抽样

> 用途：面试/复盘时被问“举几个失败例子”，不要背总准确率，直接讲下面 4 条。
> 数据：`data/evals/failures/bfcl_failures.jsonl`（31 条：10 条参数不匹配 + 21 条无关调用），
> 以及 `outputs/fixtures/fixtures_bfcl_20261105_001054.json` 的 missing 变体（2/10 通过）。
> 口径：BFCL 是**抽样 + 简化评分**，不是官方榜单；下面的例子只说明失败模式。

## 1. `simple_python_13`：数学表达式写成 `^`

- 问题：Calculate the area under the curve `y=x^2` from x=1 to x=3.
- 期望：`calculate_area_under_curve(function="x**2", interval=[1,3])`
- 实际：`function="x^2"`

**归因**：不是 schema 问题，是模型把 Python 乘方写成数学符号 `^`。工具签名没错，错在参数语义。

**处理**：工具描述/提示里写明“乘方用 `**`”，不动校验器；BFCL 60 条优化集从 55/60
到 59/60，加重复调用抑制后 60/60。**边界**：这是抽样集上的修复，不是官方分数。

## 2. `simple_python_55`：参数多了个词

- 问题：Find me detailed information about the structure of human cell.
- 期望：`cell_type="human"`
- 实际：`cell_type="human cell"`

**归因**：模型把“human cell”整体填进 `cell_type`，而 schema 要的是细胞类型 `human`。
这类错误靠 schema 校验抓不到（类型合法），只能靠 expected args 比对或更强的参数描述。

**处理**：不把它说成“模型不会调工具”；它调对了工具，只是值边界不清。该例保留在失败集，
不做特殊后处理。

## 3. `irrelevance_63`：不该调工具却调了 4 次

- 问题：How many heads can I get after tossing 3 coins?
- 期望：**no tool call**（这是纯推理题）
- 实际：连续调用 4 次 `probability_calculator`，参数还不一致

**归因**：模型把“概率”当成必须用工具的领域，产生无关调用。这类失败不是参数错，
是**决策错**；只加参数校验不会修好。

**处理**：fixture 的 `irrelevance` 分支用 `no_calls` 硬断言。它也是“为什么不能只看
工具调用成功率”的例子：调用了工具不等于做对了任务。

## 4. `simple_python_0-missing`：工具没了，模型直接心算

- 问题：已知三角形底 10、高 5，求面积。
- 期望：说明缺少面积计算工具（`cannot / unable / 缺少 / 未提供` 之类）
- 实际：直接算出 **25 square units**

**归因**：missing 变体把目标工具从工具池移除，模型没有说“工具不可用”，而是用常识补完。
这是最值得警惕的幻觉：**结果可能对，但过程绕过了评测想测的能力**。

**证据**：10 条 missing 变体只有 2 条通过（`bfcl-simple_python_1-missing`、
`bfcl-simple_python_106-missing`）；其余 8 条都是“没有工具也硬答”。这不是评分 bug，
是 fixture 想抓的行为。

**处理**：不改评分去迁就；保留 2/10，并在报告里写清楚“missing 变体是当前最大缺口”。

## 怎么引用

如果只讲一条，讲第 1 条：它展示“看 badcase → 归因到参数语义 → 只改提示 → 有分数变化 →
主动说抽样边界”。如果讲两条，加第 4 条：它展示“结果对不等于过程对”，和 outcome 评测的
主线一致。

不要做：

- 不要把这 4 条说成“BFCL 准确率”；
- 不要把 `simple_python_55` 说成工具选错；
- 不要把 missing 的失败说成“模型能力差”——它恰恰是模型太会补全。
