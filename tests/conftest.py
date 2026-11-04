# -*- coding: utf-8 -*-
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# --- Streamlit 1.40.1 AppTest 补丁（单选 button_group） ---------------------
# AppTest 的 ButtonGroup.indices 按多选实现，无条件遍历 self.value；
# st.segmented_control / st.pills 单选时 value 是标量，任何一次 run() 都会在
# 序列化上一轮 widget 状态时按字符遍历并抛 ValueError。改成同时接受标量和列表。
# 只影响测试基础设施，升级 Streamlit 后可整段删除。
try:  # pragma: no cover
    from streamlit.testing.v1 import element_tree as _element_tree
except Exception:  # pragma: no cover
    _element_tree = None


def _button_group_indices(self):
    value = self.value
    if value is None:
        return []
    values = list(value) if isinstance(value, (list, tuple)) else [value]
    format_func = self.format_func or (lambda item: item)
    return [self.options.index(format_func(item)) for item in values]


if _element_tree is not None and hasattr(_element_tree, "ButtonGroup"):
    _element_tree.ButtonGroup.indices = property(_button_group_indices)
