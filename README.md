# KnowledgeBase-RAG-LLM-System

基于 **Streamlit** 的本地知识库上传与 **RAG** 问答学习项目。

A local knowledge-base upload and **RAG** Q&A learning project built with **Streamlit**.

## 📖 文档 / Documentation

- **中文完整文档**：[docs/README.md](docs/README.md)
- **English documentation**: [docs/README.en.md](docs/README.en.md)

## 🚀 快速开始 / Quick Start

```bash
pip install -r requirements.txt
# 在项目根目录 .env 中配置 DASHSCOPE_API_KEY / set DASHSCOPE_API_KEY in .env
streamlit run app.py
```

- 支持上传 `txt` / `pdf` / `docx` / `md`，业务参数见 `config/*.yml` / Supports `txt` / `pdf` / `docx` / `md`; settings live in `config/*.yml`
- 两种对比模式：纯模型 vs RAG、纯向量 vs 混合检索 / Two comparison modes: plain LLM vs RAG, pure vector vs hybrid retrieval
- 示例知识文本 / Sample texts: `scripts/assets/`
- 运行时数据 / Runtime data: `data/`
- 冒烟测试 / Smoke test: `python scripts/smoke_test.py`

## 📄 License

See [LICENSE](LICENSE).
