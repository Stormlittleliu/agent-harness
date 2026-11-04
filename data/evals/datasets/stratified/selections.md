# 分层抽样出处记录

- 生成时间：2026-11-04T23:05:39
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
| CFBench | easy_answerable | `cfbench_data.json` | 60 | 5 |
| CFBench | easy_unanswerable | `cfbench_data.json` | 440 | 5 |
| CFBench | hard_answerable | `cfbench_data.json` | 83 | 5 |
| CFBench | hard_unanswerable | `cfbench_data.json` | 416 | 5 |
| CFBench | hard_unknown | `cfbench_data.json` | 1 | 1 |
| GAIA | level_1 | `gaia_validation.jsonl` | 53 | 5 |
| GAIA | level_2 | `gaia_validation.jsonl` | 86 | 5 |
| GAIA | level_3 | `gaia_validation.jsonl` | 26 | 5 |
| HumanEval | function_completion | `HumanEval.jsonl.gz` | 164 | 5 |
| MBPP | function_generation | `mbpp.jsonl` | 974 | 5 |
| MultiHop-RAG | comparison_query | `MultiHopRAG.json` | 856 | 5 |
| MultiHop-RAG | inference_query | `MultiHopRAG.json` | 816 | 5 |
| MultiHop-RAG | null_query | `MultiHopRAG.json` | 301 | 5 |
| MultiHop-RAG | temporal_query | `MultiHopRAG.json` | 583 | 5 |
| OSWorld | os_chrome | `examples` | 46 | 5 |
| OSWorld | os_excel | `examples` | 11 | 5 |
| OSWorld | os_gimp | `examples` | 26 | 5 |
| OSWorld | os_libreoffice_calc | `examples` | 47 | 5 |
| OSWorld | os_libreoffice_impress | `examples` | 47 | 5 |
| OSWorld | os_libreoffice_writer | `examples` | 23 | 5 |
| OSWorld | os_multi_app | `examples` | 22 | 5 |
| OSWorld | os_multi_apps | `examples` | 101 | 5 |
| OSWorld | os_os | `examples` | 24 | 5 |
| OSWorld | os_ppt | `examples` | 7 | 5 |
| OSWorld | os_thunderbird | `examples` | 15 | 5 |
| OSWorld | os_vlc | `examples` | 17 | 5 |
| OSWorld | os_vs_code | `examples` | 23 | 5 |
| OSWorld | os_word | `examples` | 9 | 5 |
| RGB | en_counterfactual | `en_fact.json` | 100 | 5 |
| RGB | en_integration | `en_int.json` | 100 | 5 |
| RGB | en_normal | `en_refine.json` | 300 | 5 |
| RGB | zh_counterfactual | `zh_fact.json` | 100 | 5 |
| RGB | zh_integration | `zh_int.json` | 100 | 5 |
| RGB | zh_normal | `zh_refine.json` | 300 | 5 |
| SWE-bench | astropy/astropy | `swebench_verified.jsonl` | 22 | 5 |
| SWE-bench | django/django | `swebench_verified.jsonl` | 231 | 5 |
| SWE-bench | matplotlib/matplotlib | `swebench_verified.jsonl` | 34 | 5 |
| SWE-bench | mwaskom/seaborn | `swebench_verified.jsonl` | 2 | 2 |
| SWE-bench | pallets/flask | `swebench_verified.jsonl` | 1 | 1 |
| SWE-bench | psf/requests | `swebench_verified.jsonl` | 8 | 5 |
| SWE-bench | pydata/xarray | `swebench_verified.jsonl` | 22 | 5 |
| SWE-bench | pylint-dev/pylint | `swebench_verified.jsonl` | 10 | 5 |
| SWE-bench | pytest-dev/pytest | `swebench_verified.jsonl` | 19 | 5 |
| SWE-bench | scikit-learn/scikit-learn | `swebench_verified.jsonl` | 32 | 5 |
| SWE-bench | sphinx-doc/sphinx | `swebench_verified.jsonl` | 44 | 5 |
| SWE-bench | sympy/sympy | `swebench_verified.jsonl` | 75 | 5 |
| WebArena | gitlab | `config_files` | 180 | 5 |
| WebArena | gitlab+reddit | `config_files` | 18 | 5 |
| WebArena | gitlab+wikipedia | `config_files` | 6 | 5 |
| WebArena | map | `config_files` | 109 | 5 |
| WebArena | map+shopping_admin | `config_files` | 2 | 2 |
| WebArena | map+wikipedia | `config_files` | 17 | 5 |
| WebArena | reddit | `config_files` | 106 | 5 |
| WebArena | reddit+shopping | `config_files` | 5 | 5 |
| WebArena | shopping | `config_files` | 187 | 5 |
| WebArena | shopping_admin | `config_files` | 182 | 5 |
| tau2-bench | airline | `tasks.json` | 50 | 5 |
| tau2-bench | banking_knowledge | `tasks.json` | 97 | 5 |
| tau2-bench | retail | `tasks.json` | 114 | 5 |
| tau2-bench | telecom | `tasks.json` | 2285 | 5 |

> `source_index` 是源文件中的 0-based 行号；`source_sha256` 是源文件内容哈希前 16 位。
