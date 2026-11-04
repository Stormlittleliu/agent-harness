# 分层抽样出处记录

- 生成时间：2026-11-04T23:14:23
- seed：42；每类目标：5 条
- 产物是平衡抽样，不是官方 benchmark 完整成绩。
- 每条样本的源文件、源文件 hash、源行号、源 id 见 `selections.jsonl`。

## 判分口径

| 类别 | 含义 | 条数 | 集合 |
|---|---|---:|---|
| 模型能力 | 只看最终输出（文本/代码/答案）；不检查工具调用或环境状态。 | 81 | CFBench, HumanEval, MBPP, MultiHop-RAG, RGB |
| 场景/工具 | 要看工具选择/参数、多轮对话或环境终态；最终输出对不算通过。 | 300 | BFCL-v4, GAIA, OSWorld, SWE-bench, WebArena, tau2-bench |

> `eval_scope` 只说明“这条 case 该怎么判”，不说明“现在能不能跑”；`execution` 才是当前执行状态（native / judge_required / sandbox_required / harness_required / tools_required）。

| benchmark | 类别 | category | 执行 | 源文件 | 源条数 | 选中 |
|---|---|---|---|---|---:|---:|
| BFCL-v4 | 场景/工具 | irrelevance | harness_required | `BFCL_v4_irrelevance.json` | 240 | 5 |
| BFCL-v4 | 场景/工具 | live_irrelevance | harness_required | `BFCL_v4_live_irrelevance.json` | 884 | 5 |
| BFCL-v4 | 场景/工具 | live_multiple | harness_required | `BFCL_v4_live_multiple.json` | 1053 | 5 |
| BFCL-v4 | 场景/工具 | live_parallel | harness_required | `BFCL_v4_live_parallel.json` | 16 | 5 |
| BFCL-v4 | 场景/工具 | live_parallel_multiple | harness_required | `BFCL_v4_live_parallel_multiple.json` | 24 | 5 |
| BFCL-v4 | 场景/工具 | live_relevance | harness_required | `BFCL_v4_live_relevance.json` | 16 | 5 |
| BFCL-v4 | 场景/工具 | live_simple | harness_required | `BFCL_v4_live_simple.json` | 258 | 5 |
| BFCL-v4 | 场景/工具 | memory | harness_required | `BFCL_v4_memory.json` | 155 | 5 |
| BFCL-v4 | 场景/工具 | multi_turn_base | harness_required | `BFCL_v4_multi_turn_base.json` | 200 | 5 |
| BFCL-v4 | 场景/工具 | multi_turn_long_context | harness_required | `BFCL_v4_multi_turn_long_context.json` | 200 | 5 |
| BFCL-v4 | 场景/工具 | multi_turn_miss_func | harness_required | `BFCL_v4_multi_turn_miss_func.json` | 200 | 5 |
| BFCL-v4 | 场景/工具 | multi_turn_miss_param | harness_required | `BFCL_v4_multi_turn_miss_param.json` | 200 | 5 |
| BFCL-v4 | 场景/工具 | multiple | harness_required | `BFCL_v4_multiple.json` | 200 | 5 |
| BFCL-v4 | 场景/工具 | parallel | harness_required | `BFCL_v4_parallel.json` | 200 | 5 |
| BFCL-v4 | 场景/工具 | parallel_multiple | harness_required | `BFCL_v4_parallel_multiple.json` | 200 | 5 |
| BFCL-v4 | 场景/工具 | simple_java | harness_required | `BFCL_v4_simple_java.json` | 100 | 5 |
| BFCL-v4 | 场景/工具 | simple_javascript | harness_required | `BFCL_v4_simple_javascript.json` | 50 | 5 |
| BFCL-v4 | 场景/工具 | simple_python | harness_required | `BFCL_v4_simple_python.json` | 400 | 5 |
| BFCL-v4 | 场景/工具 | web_search | harness_required | `BFCL_v4_web_search.json` | 100 | 5 |
| CFBench | 模型能力 | easy_answerable | judge_required | `cfbench_data.json` | 60 | 5 |
| CFBench | 模型能力 | easy_unanswerable | judge_required | `cfbench_data.json` | 440 | 5 |
| CFBench | 模型能力 | hard_answerable | judge_required | `cfbench_data.json` | 83 | 5 |
| CFBench | 模型能力 | hard_unanswerable | judge_required | `cfbench_data.json` | 416 | 5 |
| CFBench | 模型能力 | hard_unknown | judge_required | `cfbench_data.json` | 1 | 1 |
| GAIA | 场景/工具 | level_1 | tools_required | `gaia_validation.jsonl` | 53 | 5 |
| GAIA | 场景/工具 | level_2 | tools_required | `gaia_validation.jsonl` | 86 | 5 |
| GAIA | 场景/工具 | level_3 | tools_required | `gaia_validation.jsonl` | 26 | 5 |
| HumanEval | 模型能力 | function_completion | sandbox_required | `HumanEval.jsonl.gz` | 164 | 5 |
| MBPP | 模型能力 | function_generation | sandbox_required | `mbpp.jsonl` | 974 | 5 |
| MultiHop-RAG | 模型能力 | comparison_query | native | `MultiHopRAG.json` | 856 | 5 |
| MultiHop-RAG | 模型能力 | inference_query | native | `MultiHopRAG.json` | 816 | 5 |
| MultiHop-RAG | 模型能力 | null_query | native | `MultiHopRAG.json` | 301 | 5 |
| MultiHop-RAG | 模型能力 | temporal_query | native | `MultiHopRAG.json` | 583 | 5 |
| OSWorld | 场景/工具 | os_chrome | harness_required | `examples` | 46 | 5 |
| OSWorld | 场景/工具 | os_excel | harness_required | `examples` | 11 | 5 |
| OSWorld | 场景/工具 | os_gimp | harness_required | `examples` | 26 | 5 |
| OSWorld | 场景/工具 | os_libreoffice_calc | harness_required | `examples` | 47 | 5 |
| OSWorld | 场景/工具 | os_libreoffice_impress | harness_required | `examples` | 47 | 5 |
| OSWorld | 场景/工具 | os_libreoffice_writer | harness_required | `examples` | 23 | 5 |
| OSWorld | 场景/工具 | os_multi_app | harness_required | `examples` | 22 | 5 |
| OSWorld | 场景/工具 | os_multi_apps | harness_required | `examples` | 101 | 5 |
| OSWorld | 场景/工具 | os_os | harness_required | `examples` | 24 | 5 |
| OSWorld | 场景/工具 | os_ppt | harness_required | `examples` | 7 | 5 |
| OSWorld | 场景/工具 | os_thunderbird | harness_required | `examples` | 15 | 5 |
| OSWorld | 场景/工具 | os_vlc | harness_required | `examples` | 17 | 5 |
| OSWorld | 场景/工具 | os_vs_code | harness_required | `examples` | 23 | 5 |
| OSWorld | 场景/工具 | os_word | harness_required | `examples` | 9 | 5 |
| RGB | 模型能力 | en_counterfactual | native | `en_fact.json` | 100 | 5 |
| RGB | 模型能力 | en_integration | native | `en_int.json` | 100 | 5 |
| RGB | 模型能力 | en_normal | native | `en_refine.json` | 300 | 5 |
| RGB | 模型能力 | zh_counterfactual | native | `zh_fact.json` | 100 | 5 |
| RGB | 模型能力 | zh_integration | native | `zh_int.json` | 100 | 5 |
| RGB | 模型能力 | zh_normal | native | `zh_refine.json` | 300 | 5 |
| SWE-bench | 场景/工具 | astropy/astropy | harness_required | `swebench_verified.jsonl` | 22 | 5 |
| SWE-bench | 场景/工具 | django/django | harness_required | `swebench_verified.jsonl` | 231 | 5 |
| SWE-bench | 场景/工具 | matplotlib/matplotlib | harness_required | `swebench_verified.jsonl` | 34 | 5 |
| SWE-bench | 场景/工具 | mwaskom/seaborn | harness_required | `swebench_verified.jsonl` | 2 | 2 |
| SWE-bench | 场景/工具 | pallets/flask | harness_required | `swebench_verified.jsonl` | 1 | 1 |
| SWE-bench | 场景/工具 | psf/requests | harness_required | `swebench_verified.jsonl` | 8 | 5 |
| SWE-bench | 场景/工具 | pydata/xarray | harness_required | `swebench_verified.jsonl` | 22 | 5 |
| SWE-bench | 场景/工具 | pylint-dev/pylint | harness_required | `swebench_verified.jsonl` | 10 | 5 |
| SWE-bench | 场景/工具 | pytest-dev/pytest | harness_required | `swebench_verified.jsonl` | 19 | 5 |
| SWE-bench | 场景/工具 | scikit-learn/scikit-learn | harness_required | `swebench_verified.jsonl` | 32 | 5 |
| SWE-bench | 场景/工具 | sphinx-doc/sphinx | harness_required | `swebench_verified.jsonl` | 44 | 5 |
| SWE-bench | 场景/工具 | sympy/sympy | harness_required | `swebench_verified.jsonl` | 75 | 5 |
| WebArena | 场景/工具 | gitlab | harness_required | `config_files` | 180 | 5 |
| WebArena | 场景/工具 | gitlab+reddit | harness_required | `config_files` | 18 | 5 |
| WebArena | 场景/工具 | gitlab+wikipedia | harness_required | `config_files` | 6 | 5 |
| WebArena | 场景/工具 | map | harness_required | `config_files` | 109 | 5 |
| WebArena | 场景/工具 | map+shopping_admin | harness_required | `config_files` | 2 | 2 |
| WebArena | 场景/工具 | map+wikipedia | harness_required | `config_files` | 17 | 5 |
| WebArena | 场景/工具 | reddit | harness_required | `config_files` | 106 | 5 |
| WebArena | 场景/工具 | reddit+shopping | harness_required | `config_files` | 5 | 5 |
| WebArena | 场景/工具 | shopping | harness_required | `config_files` | 187 | 5 |
| WebArena | 场景/工具 | shopping_admin | harness_required | `config_files` | 182 | 5 |
| tau2-bench | 场景/工具 | airline | harness_required | `tasks.json` | 50 | 5 |
| tau2-bench | 场景/工具 | banking_knowledge | harness_required | `tasks.json` | 97 | 5 |
| tau2-bench | 场景/工具 | retail | harness_required | `tasks.json` | 114 | 5 |
| tau2-bench | 场景/工具 | telecom | harness_required | `tasks.json` | 2285 | 5 |

> `source_index` 是源文件中的 0-based 行号；`source_sha256` 是源文件内容哈希前 16 位。
