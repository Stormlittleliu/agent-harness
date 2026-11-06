# 外置数据集目录（本地数据，不进 git）

本目录是**本地 / 外置数据根**：公开 benchmark 的抽样正文、分层抽样产物、统一
benchmark catalog 都放在这里。仓库只保留：

- 本 README 与 `.gitignore`；
- `data/evals/datasets/` 下的 provenance（`selections.jsonl` / `selections.md` /
  `manifest.json`）和项目自有数据（business / selfbuilt）；
- `data/benchmarks/manifest.json` 作为 catalog 的来源引用。

默认根是 `<repo>/data/datasets`，可用环境变量指到仓库外：

```powershell
$env:AH_DATASET_ROOT = "D:\agent-harness-data"
```

代码统一通过 `core.paths.dataset_path` / `core.paths.benchmark_catalog_root`
解析，旧的 `data/evals/datasets` 布局会作为只读 fallback，已有环境不用搬数据。

## 目录约定

```text
data/datasets/
├── public/                      # RGB / MultiHop-RAG 抽样（来自 data/evals 旧布局）
│   ├── rag_rgb_sample.jsonl
│   ├── rag_multihop_sample.jsonl
│   └── multihop_corpus.json
├── stratified/                  # 每类 5 条的平衡抽样正文
│   └── *_5per_*.jsonl
└── benchmarks/                  # 统一 benchmark 样例集（派生产物）
    ├── catalog.jsonl
    ├── catalog.md
    └── manifest.json            # 与 catalog 同批生成时存在；否则回退仓库快照
```

## 生成 / 导入

```powershell
# 分层抽样：正文写到本目录 stratified/，出处记录写到 data/evals/datasets/stratified/
python -m dataset_ops.stratified --per-category 5 --seed 42

# 统一 benchmark catalog：需要先安装 AH_BENCHMARK_ROOT（见 benchmark_sources/README.md）
python -m core.benchmarks.catalog --list
python -m core.benchmarks.catalog --build --per-source 12 --seed 42
```

`public/` 下的 RGB / MultiHop 抽样是历史派生产物，没有一键生成脚本：
把已有备份（旧 `data/evals/datasets/public/` 或本目录）复制回来即可；
`core.quality.public_sample` 缺数据时会打印清晰提示，不会 traceback。

## 为什么不进 git

- **体积**：`multihop_corpus.json` 约 6.5 MB，catalog / 分层抽样正文合计数 MB；
- **许可**：RGB 源数据是 CC BY-NC-SA 4.0，不能把抽样正文直接放进 MIT 仓库；
- **可复现**：仓库保留 `selections.jsonl` 的源文件 / hash / 行号，换机器可用
  `AH_BENCHMARK_ROOT` 指到同一份上游数据后重新生成。

本目录的 `.gitignore` 忽略一切内容，只放行 `README.md` 和 `.gitignore` 自身；
`git status` 不会把数据列为待提交。旧路径的 deletion 会正常显示，表示仓库
不再跟踪这些大文件。
