# -*- coding: utf-8 -*-
"""生成面试用结构图（离线渲染，不依赖浏览器 / 不依赖网络）。

产物：
- architecture-overview.png  总图：入口 → 场景 → 契约 → 运行时 → 工具，右侧三条横切
- middleware-pipeline.png    中间件 15 个 slot 的真实顺序 + 3 条不变量
- whiteboard.png             白板版：8 个框，60 秒能徒手画完

运行：C:\\Users\\28980\\anaconda3\\python.exe docs/narrative/assets/make_diagrams.py
（matplotlib 在 base 环境；langchain 环境没装，只跑测试不用装）
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent


def pick_font() -> str:
    names = {f.name for f in font_manager.fontManager.ttflist}
    for cand in ("Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Source Han Sans SC"):
        if cand in names:
            return cand
    return "DejaVu Sans"


FONT = pick_font()
plt.rcParams.update(
    {
        "font.sans-serif": [FONT],
        "font.family": "sans-serif",
        "axes.unicode_minus": False,
    }
)

INK = "#1F2933"
MUTED = "#5B6770"
HAIR = "#C9D2DA"

C_ENTRY = ("#E9EFF8", "#3A5A8C")
C_SCEN = ("#E9F2EC", "#3E7A56")
C_SPEC = ("#F3F8EF", "#6B8E4E")
C_CONTRACT = ("#FFF3D6", "#B5811F")
C_RUNTIME = ("#ECE9F8", "#5B4A9B")
C_TOOL = ("#FAEDE7", "#A25A3F")
C_OBS = ("#E8F3F5", "#2F6F7A")


def box(
    ax,
    x,
    y,
    w,
    h,
    title,
    sub=None,
    colors=C_ENTRY,
    lw=1.3,
    tfs=11,
    sfs=7.8,
    dashed=False,
    bold=True,
    layout="center",
):
    fc, ec = colors
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0,rounding_size=1.1",
            facecolor=fc,
            edgecolor=ec,
            linewidth=lw,
            linestyle=(0, (4, 2)) if dashed else "solid",
            zorder=2,
        )
    )
    if sub is None:
        ax.text(
            x + w / 2, y + h / 2, title,
            ha="center", va="center", fontsize=tfs, fontweight="bold" if bold else "normal",
            color=INK, zorder=3, linespacing=1.4,
        )
        return
    if layout == "top":
        ty = y + h - 1.0
        ax.text(
            x + w / 2, ty, title,
            ha="center", va="top", fontsize=tfs, fontweight="bold" if bold else "normal",
            color=INK, zorder=3,
        )
        ax.text(
            x + w / 2, ty - (tfs * 0.22 + 1.1), sub,
            ha="center", va="top", fontsize=sfs, color=MUTED, zorder=3, linespacing=1.55,
        )
    else:
        ax.text(
            x + w / 2, y + h * 0.66, title,
            ha="center", va="center", fontsize=tfs, fontweight="bold" if bold else "normal",
            color=INK, zorder=3,
        )
        ax.text(
            x + w / 2, y + h * 0.30, sub,
            ha="center", va="center", fontsize=sfs, color=MUTED, zorder=3, linespacing=1.5,
        )


def arrow(ax, p1, p2, color=MUTED, lw=1.5, ls="-", rad=0.0, ms=11, style="-|>"):
    ax.add_patch(
        FancyArrowPatch(
            p1, p2,
            arrowstyle=style, mutation_scale=ms, color=color, linewidth=lw,
            linestyle=ls, shrinkA=1.2, shrinkB=1.2,
            connectionstyle=f"arc3,rad={rad}", zorder=1,
        )
    )


def elbow(ax, pts, color=MUTED, ls="-", lw=1.4, ms=10):
    """折线 + 末端箭头；拐角不做圆角，白板风格。"""
    ax.plot(
        [p[0] for p in pts[:-1]] + [pts[-1][0]],
        [p[1] for p in pts[:-1]] + [pts[-1][1]],
        color=color, linewidth=lw, linestyle=ls, solid_capstyle="butt", zorder=1,
    )
    arrow(ax, pts[-2], pts[-1], color=color, lw=lw, ls=ls, ms=ms)


def note(ax, x, y, text, fs=7.4, color=MUTED, ha="left", va="center", italic=False, bold=False, rot=0):
    ax.text(
        x, y, text, fontsize=fs, color=color, ha=ha, va=va,
        style="italic" if italic else "normal",
        fontweight="bold" if bold else "normal",
        rotation=rot, zorder=4, linespacing=1.5,
    )


def tag(ax, x, y, text, color):
    note(ax, x, y, text, fs=8.2, color=color, rot=90, bold=True)


# --------------------------------------------------------------------------
# 图 1：总图
# --------------------------------------------------------------------------
def figure_overview() -> plt.Figure:
    fig = plt.figure(figsize=(16, 9.6), dpi=220)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 160)
    ax.set_ylim(0, 96)
    ax.axis("off")

    note(ax, 7, 93.4, "my_agent_harness · 一张图", fs=14, color=INK, bold=True)
    note(
        ax, 7, 90.2,
        "场景只声明“用什么模型、哪些工具、什么提示词”，运行时统一装配；结构可以来自 spec，也可以来自代码，但只有一份运行时。",
        fs=8.4,
    )

    # ---- 入口层 ----
    tag(ax, 4.4, 80, "入口", C_ENTRY[1])
    w, gap = 32.0, 3.2
    xs = [9 + i * (w + gap) for i in range(3)]
    for x, (t, s) in zip(
        xs,
        [
            ("对话 chat.py", "已发布场景 · entry.yml"),
            ("构建 build.py", "结构编辑器 + 画布"),
            ("质量 quality.py", "评测 / 范式 / 入库"),
        ],
    ):
        box(ax, x, 78.5, w, 9.5, t, s, C_ENTRY, tfs=10.5, sfs=7.4)

    box(
        ax, 9, 71.4, 103, 5.6,
        "console/routes.py   ?app=chat|build|quality&scenario=<name>   ·   环境变量是测试后门",
        None, C_ENTRY, lw=1.1, tfs=8.2, bold=False,
    )

    # ---- 场景层 ----
    tag(ax, 4.4, 62, "场景", C_SCEN[1])
    box(
        ax, 9, 64.2, 103, 5.4,
        "library.py   界面唯一来源：有哪些场景 / 中文名 / 归属 / 是否可编辑（不再四处各说各话）",
        None, C_SCEN, lw=1.1, tfs=8.2, bold=False,
    )
    box(
        ax, 9, 52.6, 48, 9.4,
        "spec 路径",
        "data/specs/<name>/v*.json\nvalidate_spec → compile → generic.py",
        C_SPEC, tfs=10, sfs=7.4,
    )
    box(
        ax, 64, 52.6, 48, 9.4,
        "code 路径",
        "core/scenarios/<name>/graph.py\nbuild_scenario() → Scenario\n（改代码前必须先 eject）",
        C_SCEN, tfs=10, sfs=7.4,
    )

    # ---- 契约 ----
    box(
        ax, 9, 42.4, 103, 7.2,
        "Scenario 契约 · core/agent/contracts.py",
        "model · tools · system_prompt · policies · workflow_factory · planning_policy · checkpoint",
        C_CONTRACT, lw=2.0, tfs=10.5, sfs=7.4,
    )
    note(ax, 9, 40.2, "依赖方向：scenarios → contracts ← agent   （agent 不 import 任何具体场景）", fs=7.4, italic=True)

    # ---- 运行时 ----
    tag(ax, 4.4, 34, "运行时", C_RUNTIME[1])
    box(ax, 9, 27.6, 35, 11.4, "FrameworkAgent", "ReAct + checkpoint\ncreate_agent(...)", C_RUNTIME, tfs=10, sfs=7.2)
    box(ax, 47.6, 27.6, 37, 11.4, "中间件流水线", "15 策略 · 5 层\nslot 排序 + 不变量校验", C_RUNTIME, tfs=10, sfs=7.2)
    box(ax, 88, 27.6, 24, 11.4, "WorkflowRuntime", "LangGraph 图\n节点级 trace", C_RUNTIME, tfs=9.6, sfs=7.2)

    # ---- 工具 ----
    tag(ax, 4.4, 17, "工具", C_TOOL[1])
    box(ax, 9, 10.2, 24, 13.2, "模型", "DeepSeek\nfallback / retry", C_TOOL, tfs=9.8, sfs=7.0)
    box(
        ax, 36, 10.2, 44, 13.2, "工具池",
        "RAG（Chroma 元数据过滤 + BM25）\nMCP client（stdio）· 任务库 · 工作区",
        C_TOOL, tfs=9.8, sfs=7.0,
    )
    box(
        ax, 83, 10.2, 29, 13.2, "记忆与提示词",
        "checkpoint（memory/sqlite）\nprompt blocks 按真实状态拼",
        C_TOOL, tfs=9.4, sfs=7.0,
    )

    # ---- 右侧横切 ----
    note(ax, 118, 84.5, "横切：不在主流上，但每次 run 都会经过", fs=8.0, bold=True, color=C_OBS[1])

    box(
        ax, 118, 62, 38, 17, "评测 quality",
        "输入：场景库里的场景 + 自建任务\n三层口径：能力 / 行为 / 终态\nfixtures：clean·distractor·missing·failure\npass^k · outcome · 成本 · 安全\n采纳 → candidates/（不覆盖 active）",
        C_OBS, tfs=10, sfs=7.0, layout="top",
    )
    box(
        ax, 118, 34, 38, 17, "观测 observability",
        "tracer：每条事件带 node\n     tokens / 耗时 / 成本\nbudget：单次 run 的 token 上限\n→ trace_report / cost_report",
        C_OBS, tfs=10, sfs=7.2, layout="top",
    )
    box(
        ax, 118, 10.2, 38, 13, "归属 ownership",
        "spec / code 状态机\neject 是唯一写 state 的入口\n可视化读 compiled_graph\n（不读 spec，所以不会过期）",
        C_OBS, tfs=10, sfs=7.2, layout="top",
    )

    # 主流转箭头
    for x in xs:
        arrow(ax, (x + w / 2, 78.5), (x + w / 2, 77.0), ms=8)
    arrow(ax, (60.5, 71.4), (60.5, 69.6))
    arrow(ax, (33, 64.2), (33, 62.0))
    arrow(ax, (88, 64.2), (88, 62.0))
    arrow(ax, (33, 52.6), (33, 49.6))
    arrow(ax, (88, 52.6), (88, 49.6))
    arrow(ax, (60.5, 42.4), (60.5, 39.0), lw=1.8)
    arrow(ax, (26.5, 27.6), (26.5, 23.4), lw=1.8)
    arrow(ax, (66, 27.6), (66, 23.4), lw=1.8)
    arrow(ax, (100, 27.6), (100, 23.4), lw=1.8)

    # 运行时 → 观测（trace 回调）
    arrow(ax, (112, 37), (118, 37), ls=(0, (4, 2)), color=C_OBS[1], ms=9)
    # 场景库 → 评测（评测的输入就是场景库里的场景）
    arrow(ax, (112, 66.9), (118, 70.4), ls=(0, (4, 2)), color=C_OBS[1], ms=9)
    # 记忆/工具 → 归属
    arrow(ax, (112, 17), (118, 17), ls=(0, (4, 2)), color=C_OBS[1], ms=9)

    note(
        ax, 7, 5.0,
        "读图顺序：① 入口只读 entry.yml   ② 两条来源汇到同一个 Scenario   ③ 契约是唯一接缝   ④ 评测从场景库取任务，结果回流 spec（candidates/），不直接改运行时",
        fs=7.8,
    )
    return fig


# --------------------------------------------------------------------------
# 图 2：中间件真实顺序
# --------------------------------------------------------------------------
SLOT_ORDER = [
    ("permission", "权限", "守卫"),
    ("custom", "自定义", "自定义"),
    ("hooks", "钩子", "上下文"),
    ("planning", "规划", "上下文"),
    ("todo", "清单", "上下文"),
    ("summarization", "压缩", "上下文"),
    ("pii", "脱敏", "上下文"),
    ("hitl", "审批", "守卫"),
    ("timeout", "超时", "可靠"),
    ("error", "异常", "可靠"),
    ("retry", "重试", "可靠"),
    ("limit", "上限", "可靠"),
    ("budget", "预算", "成本"),
    ("fallback", "回退", "可靠"),
    ("model_retry", "模型重试", "可靠"),
]

LAYER_COLORS = {
    "守卫": ("#DCE7F6", "#3A5A8C"),
    "上下文": ("#E3EFE7", "#3E7A56"),
    "自定义": ("#EDE6F7", "#6B4E9B"),
    "可靠": ("#FBE7DC", "#A25A3F"),
    "成本": ("#FCF1D2", "#B5811F"),
}


def figure_pipeline() -> plt.Figure:
    fig = plt.figure(figsize=(16, 6.2), dpi=220)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 190)
    ax.set_ylim(0, 70)
    ax.axis("off")

    note(ax, 6, 64.8, "中间件流水线：15 个策略，按 slot 从外到内", fs=13.5, color=INK, bold=True)
    note(ax, 6, 60.8, "slot 是运行时的真实顺序；UI 的“5 层”只是分组展示。顺序不靠调用方拖拽，配错在编译期报错。", fs=8.2)

    n = len(SLOT_ORDER)
    left, right = 6, 184
    gap = 1.7
    cw = (right - left - gap * (n - 1)) / n
    y, h = 48, 11

    for i, (key, label, layer) in enumerate(SLOT_ORDER):
        x = left + i * (cw + gap)
        fc, ec = LAYER_COLORS[layer]
        ax.add_patch(
            FancyBboxPatch(
                (x, y), cw, h,
                boxstyle="round,pad=0,rounding_size=0.9",
                facecolor=fc, edgecolor=ec, linewidth=1.2, zorder=2,
            )
        )
        ax.text(x + cw / 2, y + h * 0.64, label, ha="center", va="center", fontsize=9.2, fontweight="bold", color=INK, zorder=3)
        ax.text(x + cw / 2, y + h * 0.26, key, ha="center", va="center", fontsize=6.4, color=MUTED, zorder=3)

    note(ax, left, 44.9, "模型发出一次调用 →", fs=8.0)
    note(ax, right, 44.9, "→ 工具真正执行", fs=8.0, ha="right")
    arrow(ax, (left, 43.2), (right, 43.2), lw=1.4, ms=10)
    note(ax, left, 40.6, "越靠左越先看到这次调用：权限层可以直接拒掉，后面的层就不会被调用。", fs=7.8)

    # 图例
    lx = 6
    for name, (fc, ec) in LAYER_COLORS.items():
        ax.add_patch(
            FancyBboxPatch(
                (lx, 36.6), 1.6, 1.6,
                boxstyle="round,pad=0,rounding_size=0.35",
                facecolor=fc, edgecolor=ec, linewidth=1.0, zorder=2,
            )
        )
        note(ax, lx + 2.4, 37.4, f"{name}层" if name != "自定义" else "自定义", fs=7.6)
        lx += 2.4 + (4.2 if len(name) <= 2 else 5.4) + 4.0

    # 三条不变量
    cards = [
        ("① 守卫在最外", "permission  <  hitl  <  timeout", "被拒绝的工具不该进入审批，更不该被执行；\n审批等待的时间不算工具耗时。"),
        ("② 异常在重试外", "error  <  retry", "重试耗尽后才转成中文 ToolMessage，\n让模型换一条路继续。"),
        ("③ 规划在清单外", "planning  <  todo", "先按规则决定是否委派 / 换工具，\n再进入常规 write_todos 流程。"),
    ]
    widths = [60, 56, 58]
    x = 6
    for (head, chain, why), cw2 in zip(cards, widths):
        ax.add_patch(
            FancyBboxPatch(
                (x, 12), cw2, 18,
                boxstyle="round,pad=0,rounding_size=1.1",
                facecolor="#FAFBFC", edgecolor=HAIR, linewidth=1.0, zorder=2,
            )
        )
        note(ax, x + 3, 28.6, head, fs=9.4, color=INK, bold=True, va="top")
        note(ax, x + 3, 23.4, chain, fs=7.8, color="#8A5A10", va="top")
        note(ax, x + 3, 18.2, why, fs=7.4, va="top")
        x += cw2 + 4

    note(ax, 6, 7.0, "验证点：tests/test_pipeline.py 直接断言这 3 条顺序；缺一条就红。", fs=7.2, italic=True)
    return fig


# --------------------------------------------------------------------------
# 图 3：白板版
# --------------------------------------------------------------------------
def figure_whiteboard() -> plt.Figure:
    fig = plt.figure(figsize=(12, 8.4), dpi=220)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 120)
    ax.set_ylim(0, 84)
    ax.axis("off")

    note(ax, 6, 79, "白板版：60 秒画完，再逐层加细节", fs=13, color=INK, bold=True)

    steps = [
        ("用户 / 前端", C_ENTRY),
        ("控制台 3 个产品", C_ENTRY),
        ("场景库 library.py", C_SCEN),
        ("spec 或 code（两条来源）", C_SPEC),
        ("Scenario 契约", C_CONTRACT),
        ("中间件 15 策略", C_RUNTIME),
        ("模型 + 工具", C_TOOL),
        ("trace + 评测", C_OBS),
    ]
    tips = [
        "一个 URL：/?app=chat&scenario=…",
        "发布校验：只认 entry.yml 的 enabled",
        "“有哪些场景”的唯一来源",
        "spec 即时生效；code 要先 eject",
        "唯一接缝：agent 不 import 场景",
        "顺序 = slot，不靠调用方拖",
        "工具白名单来自 spec.tools",
        "评测发现问题 → 改 spec / 加 case",
    ]
    y0, h, gap = 71.0, 5.6, 3.0
    ys = []
    for i, (label, colors) in enumerate(steps):
        y = y0 - i * (h + gap)
        ys.append(y)
        box(ax, 26, y, 56, h, label, None, colors, tfs=10.2)
        if i:
            arrow(ax, (54, y + h + gap), (54, y + h), ms=9)

    for y, text in zip(ys, tips):
        cy = y + h / 2
        ax.plot([83, 88], [cy, cy], color=HAIR, lw=1.0, zorder=1)
        note(ax, 89, cy, text, fs=7.5)

    # 回环：走左侧，不穿框
    spec_cy = ys[3] + h / 2
    trace_cy = ys[7] + h / 2
    elbow(ax, [(26, trace_cy), (11.5, trace_cy), (11.5, spec_cy), (26, spec_cy)], color=C_OBS[1], ls=(0, (4, 2)))
    note(ax, 10, (spec_cy + trace_cy) / 2, "评测回流", fs=7.4, color=C_OBS[1], rot=90, ha="center")

    note(ax, 6, 4.0, "三句话：① 一份运行时，两种来源   ② 契约在中间，依赖单向   ③ 评测回流 spec，不碰运行时", fs=8.2, bold=True)
    return fig


def main() -> None:
    for name, fn in (
        ("architecture-overview", figure_overview),
        ("middleware-pipeline", figure_pipeline),
        ("whiteboard", figure_whiteboard),
    ):
        fig = fn()
        path = OUT / f"{name}.png"
        fig.savefig(path, facecolor="white", bbox_inches="tight", pad_inches=0.25)
        plt.close(fig)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
