# RAG 检索层评测报告

- 样本总数：42
- 参与检索评分：32（排除 unanswerable）
- 分类分布：{'normal': 22, 'edge': 5, 'conflict': 5, 'unanswerable': 10}

## 汇总

| 检索模式 | Hit@K | MRR | 命中/总数 |
|:---|:---:|:---:|:---:|
| vector | 100.00% | 1.0000 | 32/32 |
| hybrid | 100.00% | 1.0000 | 32/32 |

## 明细

| ID | 类别 | 问题 | 期望来源 | vector Top-K | hybrid Top-K |
|:---|:---|:---|:---|:---|:---|
| rag-001 | normal | 身高180cm、体重165斤，推荐什么尺码？ | 尺码推荐.txt | ✅ 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 颜色推荐.txt | ✅ 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 颜色推荐.txt |
| rag-002 | normal | 身高160cm、体重100斤，推荐什么尺码？ | 尺码推荐.txt | ✅ 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 颜色推荐.txt | ✅ 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 颜色推荐.txt |
| rag-003 | normal | 真丝连衣裙怎么洗？ | 洗涤养护.txt | ✅ 洗涤养护.txt, 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md | ✅ 洗涤养护.txt, 洗涤养护.txt, 洗涤养护.txt, 颜色推荐.txt |
| rag-004 | normal | 羊毛衫可以用洗衣机洗吗？ | 洗涤养护.txt | ✅ 洗涤养护.txt, 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md | ✅ 洗涤养护.txt, 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md |
| rag-005 | normal | 羽绒服怎么洗？ | 洗涤养护.txt | ✅ 洗涤养护.txt, 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md | ✅ 洗涤养护.txt, 洗涤养护.txt, 洗涤养护.txt, 颜色推荐.txt |
| rag-006 | normal | 黄皮适合什么颜色？ | 颜色推荐.txt | ✅ 颜色推荐.txt, 颜色推荐.txt, 新品推荐.md, 尺码推荐.txt | ✅ 颜色推荐.txt, 颜色推荐.txt, 新品推荐.md, 尺码推荐.txt |
| rag-007 | normal | 正式面试穿什么颜色？ | 颜色推荐.txt | ✅ 颜色推荐.txt, 颜色推荐.txt, 新品推荐.md, 尺码推荐.txt | ✅ 颜色推荐.txt, 颜色推荐.txt, 新品推荐.md, 尺码推荐.txt |
| rag-008 | normal | 冬天想显瘦，穿什么颜色？ | 颜色推荐.txt | ✅ 颜色推荐.txt, 颜色推荐.txt, 新品推荐.md, 尺码推荐.txt | ✅ 颜色推荐.txt, 颜色推荐.txt, 新品推荐.md, 尺码推荐.txt |
| rag-009 | normal | 2026 春季新品有哪些？ | 新品推荐.md | ✅ 新品推荐.md, 洗涤养护.txt, 颜色推荐.txt, 颜色推荐.txt | ✅ 新品推荐.md, 洗涤养护.txt, 颜色推荐.txt, 颜色推荐.txt |
| rag-010 | normal | 速干运动短袖适合什么场景？ | 新品推荐.md | ✅ 新品推荐.md, 颜色推荐.txt, 尺码推荐.txt, 颜色推荐.txt | ✅ 新品推荐.md, 颜色推荐.txt, 颜色推荐.txt, 尺码推荐.txt |
| rag-011 | edge | 身高178cm、体重150斤，春天面试穿什么尺码和颜色？ | 尺码推荐.txt, 颜色推荐.txt | ✅ 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 颜色推荐.txt | ✅ 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 颜色推荐.txt |
| rag-012 | edge | 冬季羊毛大衣怎么洗、怎么收纳？ | 洗涤养护.txt | ✅ 洗涤养护.txt, 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md | ✅ 洗涤养护.txt, 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md |
| rag-013 | edge | 纯棉T恤和真丝裙子可以一起机洗吗？ | 洗涤养护.txt | ✅ 洗涤养护.txt, 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md | ✅ 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md, 洗涤养护.txt |
| rag-014 | conflict | 身高178cm、体重72kg，买 2026 春季新品防风外套，推荐什么尺码？ | 尺码推荐.txt, 新品推荐.md | ✅ 新品推荐.md, 尺码推荐.txt, 颜色推荐.txt, 颜色推荐.txt | ✅ 新品推荐.md, 尺码推荐.txt, 颜色推荐.txt, 洗涤养护.txt |
| rag-015 | conflict | 尺码表写 175-182cm、145-165斤是 2XL，但新品推荐写 175-180cm、70-75kg 是 L，到底哪个对？ | 尺码推荐.txt, 新品推荐.md | ✅ 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 颜色推荐.txt | ✅ 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 颜色推荐.txt |
| rag-016 | unanswerable | 你们支持七天无理由退货吗？ | （应拒答） | 新品推荐.md, 尺码推荐.txt, 洗涤养护.txt, 颜色推荐.txt | 新品推荐.md, 尺码推荐.txt, 洗涤养护.txt, 颜色推荐.txt |
| rag-017 | unanswerable | 发票怎么开？ | （应拒答） | 洗涤养护.txt, 颜色推荐.txt, 新品推荐.md, 洗涤养护.txt | 洗涤养护.txt, 颜色推荐.txt, 新品推荐.md, 洗涤养护.txt |
| rag-018 | unanswerable | 快递一般多久能到？ | （应拒答） | 新品推荐.md, 尺码推荐.txt, 颜色推荐.txt, 洗涤养护.txt | 新品推荐.md, 洗涤养护.txt, 尺码推荐.txt, 颜色推荐.txt |
| rag-019 | unanswerable | 会员积分怎么使用？ | （应拒答） | 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md, 洗涤养护.txt | 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md, 洗涤养护.txt |
| rag-020 | unanswerable | 你们的客服电话是多少？ | （应拒答） | 尺码推荐.txt, 新品推荐.md, 洗涤养护.txt, 颜色推荐.txt | 颜色推荐.txt, 新品推荐.md, 洗涤养护.txt, 尺码推荐.txt |
| hard-001 | normal | 我170出头，一百四十来斤，平时穿什么号？ | 尺码推荐.txt | ✅ 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 颜色推荐.txt | ✅ 尺码推荐.txt, 新品推荐.md, 洗涤养护.txt, 颜色推荐.txt |
| hard-002 | normal | 身高165厘米、体重120斤，推荐哪个尺码？ | 尺码推荐.txt | ✅ 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 颜色推荐.txt | ✅ 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 颜色推荐.txt |
| hard-003 | normal | 真丝衣服能用温水泡很久吗？ | 洗涤养护.txt | ✅ 洗涤养护.txt, 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md | ✅ 洗涤养护.txt, 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md |
| hard-004 | normal | 羊绒大衣能自己水洗吗？ | 洗涤养护.txt | ✅ 洗涤养护.txt, 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md | ✅ 洗涤养护.txt, 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md |
| hard-005 | normal | 皮肤偏黄，想买显白一点的上衣，推荐什么颜色？ | 颜色推荐.txt | ✅ 颜色推荐.txt, 颜色推荐.txt, 新品推荐.md, 尺码推荐.txt | ✅ 颜色推荐.txt, 新品推荐.md, 颜色推荐.txt, 尺码推荐.txt |
| hard-006 | normal | 参加婚礼穿什么颜色合适？ | 颜色推荐.txt | ✅ 颜色推荐.txt, 颜色推荐.txt, 新品推荐.md, 尺码推荐.txt | ✅ 颜色推荐.txt, 颜色推荐.txt, 新品推荐.md, 尺码推荐.txt |
| hard-007 | normal | 春天早晚温差大，新品里有什么外套推荐？ | 新品推荐.md | ✅ 新品推荐.md, 颜色推荐.txt, 洗涤养护.txt, 洗涤养护.txt | ✅ 新品推荐.md, 洗涤养护.txt, 洗涤养护.txt, 颜色推荐.txt |
| hard-008 | normal | 敏感肌适合哪套家居服？ | 新品推荐.md | ✅ 新品推荐.md, 洗涤养护.txt, 颜色推荐.txt, 洗涤养护.txt | ✅ 新品推荐.md, 颜色推荐.txt, 洗涤养护.txt, 颜色推荐.txt |
| hard-009 | normal | 羊毛衫洗完能挂起来晾吗？ | 洗涤养护.txt | ✅ 洗涤养护.txt, 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md | ✅ 洗涤养护.txt, 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md |
| hard-010 | normal | 纯棉T恤第一次洗要注意什么？ | 洗涤养护.txt | ✅ 洗涤养护.txt, 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md | ✅ 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md, 洗涤养护.txt |
| hard-011 | normal | 羽绒服洗完怎么恢复蓬松？ | 洗涤养护.txt | ✅ 洗涤养护.txt, 洗涤养护.txt, 洗涤养护.txt, 新品推荐.md | ✅ 洗涤养护.txt, 洗涤养护.txt, 颜色推荐.txt, 洗涤养护.txt |
| hard-012 | normal | 个子不高、偏瘦，穿浅色还是深色更显高？ | 颜色推荐.txt | ✅ 颜色推荐.txt, 颜色推荐.txt, 新品推荐.md, 尺码推荐.txt | ✅ 颜色推荐.txt, 新品推荐.md, 颜色推荐.txt, 洗涤养护.txt |
| hard-013 | conflict | 身高178cm、体重72kg，春季新品防风外套穿L还是XL？ | 尺码推荐.txt, 新品推荐.md | ✅ 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 洗涤养护.txt | ✅ 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 洗涤养护.txt |
| hard-014 | conflict | 尺码表说175-182cm、145-165斤是2XL，新品却说175-180cm、70-75kg是L，哪个准？ | 尺码推荐.txt, 新品推荐.md | ✅ 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 颜色推荐.txt | ✅ 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 颜色推荐.txt |
| hard-015 | conflict | 我身高176、体重73公斤，按尺码表和新品推荐分别是什么码？ | 尺码推荐.txt, 新品推荐.md | ✅ 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 颜色推荐.txt | ✅ 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 颜色推荐.txt |
| hard-016 | unanswerable | 你们支持七天无理由退货吗？ | （应拒答） | 新品推荐.md, 尺码推荐.txt, 洗涤养护.txt, 颜色推荐.txt | 新品推荐.md, 尺码推荐.txt, 洗涤养护.txt, 颜色推荐.txt |
| hard-017 | unanswerable | 怎么开发票？ | （应拒答） | 颜色推荐.txt, 洗涤养护.txt, 新品推荐.md, 洗涤养护.txt | 颜色推荐.txt, 洗涤养护.txt, 新品推荐.md, 洗涤养护.txt |
| hard-018 | unanswerable | 发什么快递，几天能到？ | （应拒答） | 新品推荐.md, 尺码推荐.txt, 颜色推荐.txt, 洗涤养护.txt | 尺码推荐.txt, 洗涤养护.txt, 新品推荐.md, 洗涤养护.txt |
| hard-019 | unanswerable | 会员积分能抵现吗？ | （应拒答） | 新品推荐.md, 洗涤养护.txt, 尺码推荐.txt, 洗涤养护.txt | 洗涤养护.txt, 新品推荐.md, 洗涤养护.txt, 尺码推荐.txt |
| hard-020 | unanswerable | 蔡徐坤是谁？ | （应拒答） | 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt, 洗涤养护.txt | 颜色推荐.txt, 尺码推荐.txt, 新品推荐.md, 颜色推荐.txt |
| hard-021 | edge | 身高180、体重160斤，黄皮，参加婚礼穿什么颜色和尺码？ | 尺码推荐.txt, 颜色推荐.txt | ✅ 尺码推荐.txt, 颜色推荐.txt, 颜色推荐.txt, 新品推荐.md | ✅ 尺码推荐.txt, 颜色推荐.txt, 新品推荐.md, 颜色推荐.txt |
| hard-022 | edge | 冬天穿羊毛大衣去面试，怎么洗、穿什么颜色？ | 洗涤养护.txt, 颜色推荐.txt | ✅ 颜色推荐.txt, 颜色推荐.txt, 洗涤养护.txt, 洗涤养护.txt | ✅ 颜色推荐.txt, 洗涤养护.txt, 颜色推荐.txt, 洗涤养护.txt |
