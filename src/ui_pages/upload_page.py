"""知识库上传页面：上传 txt/pdf/docx/md -> 解析 -> 按类型切片 -> 写入 Chroma。"""
import time

import streamlit as st

from kbrag import config
from kbrag.document_parser import get_file_type, parse_document
from kbrag.knowledge_base import KnowledgeBaseService


def upload_page():
    # 添加网页标题
    st.title("知识库更新服务")
    st.caption(
        "支持 " + " / ".join(config.allow_file_types) + " 格式；"
        "不同格式会在入库时使用 config/chroma.yml 中各自配置的切片参数。"
    )

    # file_uploader
    uploader_file = st.file_uploader(
        "请上传文档",
        type=config.allow_file_types,
        accept_multiple_files=False,  # False表示仅接受一个文件的上传
    )

    if "service" not in st.session_state:  # 会话状态字典，session_state本身也是字典
        st.session_state["service"] = KnowledgeBaseService()

    if uploader_file is not None:
        # 提取文件信息
        file_name = uploader_file.name
        file_type = get_file_type(file_name)
        file_size = uploader_file.size / 1024
        st.subheader(f"文件名:{file_name}")
        st.write(f"格式:{file_type}  | 大小:{file_size:.2f}KB")

        with st.spinner("解析并载入知识库中。。。"):  # 在 spinner 内执行时会显示转圈动画
            time.sleep(1)
            try:
                # 先在内存中完成解析：解析失败时不会写入知识库
                text = parse_document(uploader_file.getvalue(), file_name)
                result = st.session_state["service"].upload_by_str(
                    text, file_name, file_type=file_type,
                )
            except ValueError as exc:
                st.error(f"上传失败：{exc}")
            else:
                st.write(result)
