# -*- coding: utf-8 -*-
"""场景编辑器的画布组件：把工作流画成可拖拽的节点图。

前端是 ``canvas/index.html``——单文件、无 npm、无 CDN，自带一个很小的拖拽图编辑器；
和后端只交换 JSON：

    后端 -> 前端  {nodes:[{id, fn, label, x, y, kind?}], edges:[[from,to] 或 [from,to,when]], blocks,
                   show_palette, errors, selected}
    前端 -> 后端  {nodes:[{id, fn, x, y, copy_of?}], edges, anchors:{__start__:[x,y]},
                   selected, version}
               或 {command: "undo"|"redo", version}（快捷键只发命令，历史在 Python 侧）

约定：**画布改拓扑、位置和边条件**。节点参数仍走右侧检查器；节点 id 的合法性、块是否存在、
边是否悬空，全部回到 ``core.scenarios.spec_edit`` 里再校验一遍——前端传来的一律当不可信输入。
"""
from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components

_CANVAS_DIR = Path(__file__).with_name("canvas")
_component = components.declare_component("scenario_canvas", path=str(_CANVAS_DIR))


def render_canvas(payload: dict, *, key: str) -> dict | None:
    """渲染画布；用户还没操作过时返回 None。"""
    return _component(payload=payload, key=key, default=None)
