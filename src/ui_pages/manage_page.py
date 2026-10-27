"""向量库管理页面：查看分块、按文档删除、清空向量库。"""
import streamlit as st

from kbrag import config
from kbrag.knowledge_base import KnowledgeBaseService


def _show_flash():
    """显示上一次操作的结果；消息只展示一次"""
    if "manage_flash" not in st.session_state:
        return
    kind, message = st.session_state["manage_flash"]
    del st.session_state["manage_flash"]
    getattr(st, kind)(message)


def _rerun_with_flash(kind, message):
    """把提示存入会话状态后刷新页面，避免刷新后提示丢失"""
    st.session_state["manage_flash"] = (kind, message)
    st.rerun()


def _build_summary(chunks):
    """按来源文件汇总分块数量、最近入库时间和操作人"""
    grouped = {}
    for chunk in chunks:
        source = chunk["source"]
        item = grouped.setdefault(source, {
            "来源文件": source,
            "文件类型": set(),
            "分块数": 0,
            "最近入库时间": "",
            "操作人": set(),
        })
        item["分块数"] += 1
        if chunk["file_type"]:
            item["文件类型"].add(chunk["file_type"])
        if chunk["create_time"] > item["最近入库时间"]:
            item["最近入库时间"] = chunk["create_time"]
        if chunk["operator"]:
            item["操作人"].add(chunk["operator"])

    rows = []
    for item in sorted(grouped.values(), key=lambda row: row["来源文件"]):
        # 旧数据没有 file_type 元数据，统一显示为“未知”
        item["文件类型"] = "、".join(sorted(item["文件类型"])) or "未知"
        item["操作人"] = "、".join(sorted(item["操作人"])) or "-"
        rows.append(item)
    return rows


def manage_page():
    st.title("向量库管理")
    st.caption(
        "查看已入库的分块，按文档删除或清空整个向量库。"
        "删除文档时会同步清理去重记录，之后可以重新上传同一个文件。"
    )

    _show_flash()

    # 每次页面运行都重新创建服务，确保能读到其他页面刚写入的最新数据
    try:
        service = KnowledgeBaseService()
        chunks = service.list_chunks()
        md5_count = service.count_md5_records()
    except Exception as exc:
        st.error(f"读取向量库失败：{exc}")
        return

    sources = sorted({chunk["source"] for chunk in chunks})

    col1, col2, col3 = st.columns(3)
    col1.metric("分块总数", len(chunks))
    col2.metric("文档数", len(sources))
    col3.metric("去重记录", md5_count)
    st.caption(
        f"集合：`{config.collection_name}` ｜ "
        f"存储目录：`{config.persist_directory}`"
    )

    if not chunks:
        st.info("当前向量库为空，请先到“知识库上传”页面导入文档。")
        return

    st.divider()
    st.subheader("文档列表")
    st.dataframe(_build_summary(chunks), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("查看分块")
    selected_source = st.selectbox("选择来源文件", sources)
    selected_chunks = [chunk for chunk in chunks if chunk["source"] == selected_source]
    for index, chunk in enumerate(selected_chunks, 1):
        with st.expander(f"分块 {index} · {chunk['length']} 字符"):
            st.text(chunk["content"])
            st.caption(
                f"ID：{chunk['id']} ｜ "
                f"类型：{chunk['file_type'] or '未知'} ｜ "
                f"入库时间：{chunk['create_time'] or '-'} ｜ "
                f"操作人：{chunk['operator'] or '-'}"
            )

    st.divider()
    st.subheader("删除文档")
    st.caption("删除某个来源的全部分块，并移除它的 MD5 去重记录。该操作不可撤销。")
    with st.form("delete_source_form", clear_on_submit=True):
        target = st.selectbox("要删除的来源文件", sources, key="delete_source_target")
        confirmed = st.checkbox("我确认删除该文档的全部分块及去重记录")
        submitted = st.form_submit_button("删除文档")
        if submitted:
            if not confirmed:
                st.warning("请先勾选确认后再删除。")
            else:
                try:
                    deleted = service.delete_by_source(target)
                except Exception as exc:
                    st.error(f"删除失败：{exc}")
                else:
                    _rerun_with_flash(
                        "success",
                        f"已删除 {target} 的 {deleted} 个分块，并清理对应去重记录。",
                    )

    st.divider()
    st.subheader("清空向量库")
    st.caption("清空全部分块和 MD5 去重记录。该操作不可撤销，请谨慎操作。")
    with st.form("clear_all_form", clear_on_submit=True):
        confirmed_all = st.checkbox("我确认清空整个向量库及全部去重记录")
        submitted_all = st.form_submit_button("清空向量库")
        if submitted_all:
            if not confirmed_all:
                st.warning("请先勾选确认后再清空。")
            else:
                try:
                    deleted = service.clear_all()
                except Exception as exc:
                    st.error(f"清空失败：{exc}")
                else:
                    _rerun_with_flash(
                        "success",
                        f"已清空向量库，共删除 {deleted} 个分块。",
                    )
