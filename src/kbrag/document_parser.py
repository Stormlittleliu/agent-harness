"""多格式文档解析：把上传文件的字节内容解析为纯文本。

支持格式与实现方式：
- txt / md：按 UTF-8 解码（失败时回退 GBK，兼容 Windows 常见中文文本）
- pdf：交给 pypdf 逐页提取文字，页与页之间保留空行
- docx：交给 python-docx 提取段落与表格文字

解析失败一律抛出带中文说明的 ValueError，由页面层捕获并提示用户。
"""
import os
from io import BytesIO

from pypdf import PdfReader

try:  # python-docx 属于可选依赖，未安装时不影响其他格式的解析
    from docx import Document
except ImportError:  # pragma: no cover - 环境缺依赖时的提示分支
    Document = None

# 文本类文件（没有复杂结构，直接解码即可）
TEXT_FILE_TYPES = ("txt", "md")


def get_file_type(filename: str) -> str:
    """从文件名中取出小写扩展名（不含点）。"""
    return os.path.splitext(str(filename))[1].lower().lstrip(".")


def parse_document(content: bytes, filename: str) -> str:
    """把文件字节内容解析为纯文本。

    :param content: 文件二进制内容
    :param filename: 原始文件名（用于判断文档类型）
    :return: 解析后的纯文本
    :raises ValueError: 文件类型不支持或内容无法解析时抛出中文错误
    """
    if not content:
        raise ValueError("文件内容为空，无法解析")

    file_type = get_file_type(filename)
    if file_type in TEXT_FILE_TYPES:
        return _decode_text(content)
    if file_type == "pdf":
        return _parse_pdf(content)
    if file_type == "docx":
        return _parse_docx(content)
    raise ValueError(f"暂不支持的文件类型：{file_type or '(无扩展名)'}")


def _decode_text(content: bytes) -> str:
    """文本文件解码：优先 UTF-8，失败后按 GBK 再试一次。"""
    for encoding in ("utf-8", "gbk"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("文本文件编码无法识别（请另存为 UTF-8 后重试）")


def _parse_pdf(content: bytes) -> str:
    """PDF 解析：逐页提取文字，页间用空行分隔（保留分页边界）。"""
    try:
        reader = PdfReader(BytesIO(content))
    except Exception as exc:
        raise ValueError(f"PDF 文件无法读取：{exc}") from exc

    pages = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception:
            # 单页解析失败不影响其他页，跳过后继续
            text = ""
        if text.strip():
            pages.append(text.strip())

    if not pages:
        raise ValueError("PDF 未提取到文字（可能是扫描件，需要先做 OCR）")
    # 页间保留空行，正好对应切片参数里的第一个分隔符 "\n\n"
    return "\n\n".join(pages)


def _parse_docx(content: bytes) -> str:
    """DOCX 解析：先提取正文段落，再提取表格（表格每行合并为一段文字）。"""
    if Document is None:
        raise ValueError("缺少 python-docx 依赖，无法解析 docx（pip install python-docx）")

    try:
        document = Document(BytesIO(content))
    except Exception as exc:
        raise ValueError(f"docx 文件无法读取：{exc}") from exc

    blocks = []
    # 正文段落：跳过空段落
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            blocks.append(text)

    # 表格：每个单元格单独成段，保证表格里的知识也能被检索到
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                blocks.append(" | ".join(cells))

    if not blocks:
        raise ValueError("docx 中没有可提取的文字内容")
    return "\n".join(blocks)
