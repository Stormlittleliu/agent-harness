# 知识库分类与领域特化场景

> 目标：同一套 Chroma 里放扫地机器人 + 服装两域知识，但检索时**只召回当前域**；
> 再用两个 spec 场景展示「特化工作流」和「判断分流」。

## 1. 服装知识从哪来

服装域文档原本在：

```text
data/evals/datasets/business/docs/
  尺码推荐.txt
  颜色推荐.txt
  洗涤养护.txt
  新品推荐.md
```

现在复制到 `data/knowledge/`，加 `服装-` 前缀，避免和机器人文档同名：

```text
data/knowledge/
  服装-尺码推荐.txt
  服装-颜色推荐.txt
  服装-洗涤养护.txt
  服装-新品推荐.md
  扫地机器人100问.pdf
  扫地机器人100问2.txt
  扫拖一体机器人100问.txt
  故障排除.txt
  维护保养.txt
  选购指南.txt
```

原文件保留在 `data/evals/datasets/business/docs/`，评测集不受影响。

## 2. 分类是入库元数据

`core/tools/rag/classification.py` 在入库时给每个分块打：

```json
{
  "domain": "clothing",
  "category": "size",
  "source": "服装-尺码推荐.txt"
}
```

规则：

| domain | category | 来源 |
|---|---|---|
| robot | faq | 扫地机器人100问 / 扫拖一体100问 |
| robot | troubleshoot | 故障排除 |
| robot | maintenance | 维护保养 |
| robot | purchase | 选购指南 |
| clothing | size | 尺码推荐 |
| clothing | color | 颜色推荐 |
| clothing | care | 洗涤养护 |
| clothing | new | 新品推荐 |

文件名优先，正文关键词兜底；都不命中归 `general/uncategorized`。
**这不是让模型分类**，所以同一份文档每次入库的 domain/category 是稳定的。

## 3. 检索过滤

`VectorStoreService.get_retriever(where=...)` 把 `where` 传给 Chroma；
hybrid 模式同时用同一个 `where` 过滤 BM25 语料，避免“向量过滤了、关键词仍召回另一域”。

```python
RagSummarizeService(where={"domain": "clothing"})
RagSummarizeService(where={"domain": "robot"})
```

`core/tools/rag/tools.py` 的 `build_rag_tools(where=..., summarize_name=..., retrieve_name=...)`
让同一个工具箱里可以放两套工具：

```text
retail_expert 工具箱
  robot_retrieve      -> domain=robot
  clothing_retrieve   -> domain=clothing
```

## 4. 两个 spec 场景

### clothing_service：领域特化 + 出界拒答

```text
START → triage（服装关键词？）
          ├─ hit  → search（clothing_retrieve）→ answer → verify → END
          └─ miss → refuse（固定话术）→ END
```

- 只允许 `clothing_retrieve`，不可能召回机器人文档；
- 问“帮我写代码”会走 refuse，不硬答；
- 回答要求 `[来源id]`，`require_citation` 做确定性校验。

### retail_router：判断分流

```text
START → classify（扫地/机器人关键词？）
          ├─ robot    → robot_search（robot_retrieve）
          └─ clothing → clothing_search（clothing_retrieve）
                              ↓
                         answer → verify → END
```

- 两个检索分支不交叉；
- 分支值写 `scratch.route`，由 spec 的条件边选择；
- 在编辑器里能看到 branch 的两条条件边，适合演示“手动搭场景”。

## 5. 重新入库

```powershell
python -m core.tools.rag.vector_store --rebuild
```

`--rebuild` 会清空当前 collection 和 md5 记录，按 `data/knowledge` 重新计算 embedding。
这是本地知识库结构升级，不是增量更新；日常新增文档直接 `load_document()` 即可。

分类统计：

```powershell
python -m core.tools.rag.classification
```

控制台：质量 → 看资产 → 知识库，按 domain/category/源文件查看分块。

## 6. 边界

- 分类规则是静态的；新增领域要补 `SOURCE_RULES` / `CONTENT_RULES`；
- 服装文档按语义分块后均匀取样（每篇最多 6 块），当前共 12 个分块；适合演示，不足以代表服装领域全量；
- 检索过滤能保证“不串域”，但不能保证答案一定正确；
- 两个 spec 场景已有抽样用例（clothing 6 条、retail 5 条），3-trial pass^k 分别为 6/6、5/5；
  样本仍小，不能当领域全量质量结论。
