# 分层抽样出处记录

- 生成时间：2026-11-04T22:21:25
- seed：42；每类目标：5 条
- 产物是平衡抽样，不是官方 benchmark 完整成绩。
- 每条样本的源文件、源文件 hash、源行号、源 id 见 `selections.jsonl`。

| benchmark | category | 源文件 | 源条数 | 选中 |
|---|---|---|---:|---:|
| BFCL-v4 | irrelevance | `BFCL_v4_irrelevance.json` | 240 | 5 |
| BFCL-v4 | live_irrelevance | `BFCL_v4_live_irrelevance.json` | 884 | 5 |
| BFCL-v4 | live_multiple | `BFCL_v4_live_multiple.json` | 1053 | 5 |
| BFCL-v4 | live_parallel | `BFCL_v4_live_parallel.json` | 16 | 5 |
| BFCL-v4 | live_parallel_multiple | `BFCL_v4_live_parallel_multiple.json` | 24 | 5 |
| BFCL-v4 | live_relevance | `BFCL_v4_live_relevance.json` | 16 | 5 |
| BFCL-v4 | live_simple | `BFCL_v4_live_simple.json` | 258 | 5 |
| BFCL-v4 | memory | `BFCL_v4_memory.json` | 155 | 5 |
| BFCL-v4 | multi_turn_base | `BFCL_v4_multi_turn_base.json` | 200 | 5 |
| BFCL-v4 | multi_turn_long_context | `BFCL_v4_multi_turn_long_context.json` | 200 | 5 |
| BFCL-v4 | multi_turn_miss_func | `BFCL_v4_multi_turn_miss_func.json` | 200 | 5 |
| BFCL-v4 | multi_turn_miss_param | `BFCL_v4_multi_turn_miss_param.json` | 200 | 5 |
| BFCL-v4 | multiple | `BFCL_v4_multiple.json` | 200 | 5 |
| BFCL-v4 | parallel | `BFCL_v4_parallel.json` | 200 | 5 |
| BFCL-v4 | parallel_multiple | `BFCL_v4_parallel_multiple.json` | 200 | 5 |
| BFCL-v4 | simple_java | `BFCL_v4_simple_java.json` | 100 | 5 |
| BFCL-v4 | simple_javascript | `BFCL_v4_simple_javascript.json` | 50 | 5 |
| BFCL-v4 | simple_python | `BFCL_v4_simple_python.json` | 400 | 5 |
| BFCL-v4 | web_search | `BFCL_v4_web_search.json` | 100 | 5 |
| MultiHop-RAG | comparison_query | `MultiHopRAG.json` | 856 | 5 |
| MultiHop-RAG | inference_query | `MultiHopRAG.json` | 816 | 5 |
| MultiHop-RAG | null_query | `MultiHopRAG.json` | 301 | 5 |
| MultiHop-RAG | temporal_query | `MultiHopRAG.json` | 583 | 5 |
| RGB | en_counterfactual | `en_fact.json` | 100 | 5 |
| RGB | en_integration | `en_int.json` | 100 | 5 |
| RGB | en_normal | `en_refine.json` | 300 | 5 |
| RGB | zh_counterfactual | `zh_fact.json` | 100 | 5 |
| RGB | zh_integration | `zh_int.json` | 100 | 5 |
| RGB | zh_normal | `zh_refine.json` | 300 | 5 |
| tau2-bench | airline | `tasks.json` | 50 | 5 |
| tau2-bench | banking_knowledge | `tasks.json` | 97 | 5 |
| tau2-bench | retail | `tasks.json` | 114 | 5 |
| tau2-bench | telecom | `tasks.json` | 2285 | 5 |

> `source_index` 是源文件中的 0-based 行号；`source_sha256` 是源文件内容哈希前 16 位。
