"""RAG 对比页面：支持「纯模型 vs RAG」与「纯向量 vs 混合检索」两种模式。"""
import streamlit as st

from kbrag.compare_service import (
    MODE_PLAIN_VS_RAG,
    MODE_VECTOR_VS_HYBRID,
    load_records,
    run_compare,
    save_records,
)

# 页面展示的选项文字 -> 内部模式标识
MODE_OPTIONS = {
    "纯模型 vs RAG": MODE_PLAIN_VS_RAG,
    "纯向量 vs 混合检索": MODE_VECTOR_VS_HYBRID,
}


def _render_sources(sources, title="检索到的参考资料"):
    """展示检索命中的参考资料（来源 + 片段）。"""
    with st.expander(f"{title}（{len(sources)} 条）"):
        if not sources:
            st.write("未检索到相关内容")
        for source in sources:
            st.markdown(f"**{source['source']}**")
            st.text(source["content"])


def compare_page():
    st.title("RAG 前后对比")
    st.caption(
        "模式一：纯模型 vs RAG，直观看出录入知识库前后的区别；"
        "模式二：纯向量 vs 向量 + 关键词混合检索，观察关键词兜底带来的召回差异。"
    )

    mode_label = st.radio("对比模式", list(MODE_OPTIONS.keys()), horizontal=True)
    mode = MODE_OPTIONS[mode_label]

    if "comparisons" not in st.session_state:
        st.session_state["comparisons"] = load_records()

    with st.form("compare_form", clear_on_submit=True):
        question = st.text_input(
            "输入要对比的问题",
            placeholder="例如：根据文档，蔡徐坤2026年发行了什么专辑？",
        )
        submitted = st.form_submit_button("生成对比")

    if submitted and question.strip():
        with st.spinner("两种模式生成中，请稍候..."):
            try:
                record = run_compare(question.strip(), mode=mode)
                st.session_state["comparisons"].insert(0, record)
                save_records(st.session_state["comparisons"])
                st.rerun()
            except Exception as exc:
                st.error(f"生成失败：{exc}")

    if not st.session_state["comparisons"]:
        st.info("还没有对比记录，输入一个问题开始。")

    for record in st.session_state["comparisons"]:
        # 旧记录没有 mode 字段，按「纯模型 vs RAG」兼容展示
        record_mode = record.get("mode", MODE_PLAIN_VS_RAG)

        st.divider()
        st.subheader(f"Q：{record['question']}")
        caption = (
            f"{record.get('time', '')} | 模型：{record.get('model', '')} | "
            f"top-k：{record.get('retrieval_k', '')}"
        )
        if record_mode == MODE_PLAIN_VS_RAG:
            caption += f" | 检索模式：{record.get('retrieval_mode', '')}"
        else:
            weights = record.get("hybrid_weights") or {}
            caption += (
                f" | 融合权重：向量 {weights.get('vector', '-')} / "
                f"BM25 {weights.get('bm25', '-')}"
            )
        st.caption(caption)

        left, right = st.columns(2)
        if record_mode == MODE_VECTOR_VS_HYBRID:
            with left:
                st.markdown("#### 纯向量检索")
                st.write(record.get("vector", ""))
                _render_sources(record.get("sources_vector") or [], "向量检索命中")
            with right:
                st.markdown("#### 向量 + 关键词混合检索")
                st.write(record.get("hybrid", ""))
                _render_sources(record.get("sources_hybrid") or [], "混合检索命中")
        else:
            with left:
                st.markdown("#### 未使用知识库（纯模型）")
                st.write(record.get("plain", ""))
            with right:
                st.markdown("#### 使用知识库（RAG）")
                st.write(record.get("rag", ""))
                _render_sources(record.get("sources") or [])

    with st.sidebar:
        st.subheader("对比记录")
        st.caption(f"共 {len(st.session_state['comparisons'])} 条")
        if st.button("清空对比记录"):
            save_records([])
            st.session_state["comparisons"] = []
            st.rerun()
