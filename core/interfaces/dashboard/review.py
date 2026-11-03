# -*- coding: utf-8 -*-
"""复核视图：LLM judge + 人工标注的统一界面。

数据来自 ``python -m core.quality.review build --run outputs/selfbuilt/*.json``；
这个视图只读写复核 JSONL，不重新跑模型。
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from core.quality.paths import OUTPUTS_DIR
from core.quality.review import ISSUES, LABELS, load_review, save_review, set_label, summarize

REVIEW_DIR = Path(OUTPUTS_DIR) / "selfbuilt"


def _review_files() -> list[Path]:
    return sorted(REVIEW_DIR.glob("review_*.jsonl"), reverse=True)


def _badge(row: dict) -> str:
    auto = "自动✅" if row["auto"]["passed"] else "自动❌"
    judge = (row.get("judge") or {}).get("verdict")
    judged = {"pass": "judge✅", "partial": "judge🟡", "fail": "judge❌"}.get(judge, "judge—")
    human = (row.get("human") or {}).get("label")
    labelled = {"pass": "人工✅", "fail": "人工❌", "unsure": "人工🟡"}.get(human, "人工—")
    return f"{auto} {judged} {labelled}"


def _passes_filter(row: dict, mode: str) -> bool:
    human = row.get("human")
    judge = (row.get("judge") or {}).get("verdict")
    auto = bool(row["auto"]["passed"])
    judge_pass = None if judge is None else judge == "pass"
    if mode == "未标注":
        return human is None
    if mode == "只看不通过":
        return not auto
    if mode == "只看分歧":
        return (judge_pass is not None and judge_pass != auto) or (
            human is not None and human != "unsure" and (human == "pass") != auto
        )
    return True


def render_review() -> None:
    st.markdown("### 🧾 复核")
    st.caption("LLM judge + 人工标注；只读写复核 JSONL，不触发模型调用。")

    files = _review_files()
    if not files:
        st.warning(
            "还没有复核文件。先跑："
            "`python -m core.quality.review build --run outputs/selfbuilt/selfbuilt_xxx.json`"
        )
        return

    names = [path.name for path in files]
    choice = st.selectbox("复核文件", names, index=0, key="review-file")
    path = REVIEW_DIR / choice
    rows = load_review(path)
    report = summarize(rows)

    cols = st.columns(6)
    cols[0].metric("总数", report["total"])
    cols[1].metric("自动通过", report["auto_pass"])
    cols[2].metric("judge 通过", report["judge_pass"])
    cols[3].metric("已标注", report["labeled"])
    cols[4].metric("auto/judge 分歧", len(report["auto_vs_judge_disagreements"]))
    cols[5].metric("未标注", report["unlabeled"])

    left, right = st.columns([2, 3])
    with left:
        mode = st.radio("筛选", ["全部", "未标注", "只看分歧", "只看不通过"], horizontal=True)
    with right:
        keyword = st.text_input("搜索 id / 问题", key="review-search")

    visible = [
        row
        for row in rows
        if _passes_filter(row, mode)
        and (not keyword or keyword in row["key"] or keyword in str(row.get("question", "")))
    ]
    st.caption(f"当前显示 {len(visible)} / {len(rows)} 条")

    for row in visible:
        with st.expander(f"{row['key']} · {row.get('cell')} · {_badge(row)}", expanded=False):
            st.markdown(f"**问题**：{row.get('question') or '（无）'}")
            if row.get("expected_points"):
                st.markdown(f"**期望要点**：{'、'.join(row['expected_points'])}")
            if row.get("expected_tools"):
                st.markdown(f"**期望工具**：{'、'.join(row['expected_tools'])}")
            if row.get("expected_sources"):
                st.markdown(f"**期望来源**：{'、'.join(row['expected_sources'])}")
            st.markdown(f"**实际工具**：{'、'.join(row.get('tool_names') or []) or '（无）'}")
            st.text_area(
                "回答",
                value=row.get("answer") or "（无）",
                height=200,
                disabled=True,
                key=f"rev-ans-{row['key']}",
            )

            judge = row.get("judge") or {}
            if judge:
                st.markdown(
                    f"**judge**：{judge.get('verdict')}｜coverage {judge.get('coverage')}"
                    f"｜{judge.get('reason')}"
                )
            if row["auto"].get("error"):
                st.error(f"运行错误：{row['auto']['error']}")

            human = row.get("human") or {}
            if human:
                st.caption(
                    f"当前标注：{human.get('label', '—')}｜问题：{human.get('issue') or '—'}"
                    f"｜备注：{human.get('note') or '—'}"
                )

            issue_options = ["（未分类）", *ISSUES]
            issue = st.selectbox(
                "问题类型",
                issue_options,
                index=issue_options.index(human["issue"]) if human.get("issue") in issue_options else 0,
                key=f"rev-issue-{row['key']}",
            )
            note = st.text_area(
                "我的判断（检索没召回？工具调错？要点词不匹配？）",
                value=human.get("note", ""),
                height=100,
                key=f"rev-note-{row['key']}",
            )
            issue_value = None if issue == "（未分类）" else issue

            c1, c2, c3, c4, c5 = st.columns(5)
            if c1.button("通过", key=f"rev-pass-{row['key']}"):
                set_label(rows, row["key"], "pass", note, issue_value)
                save_review(rows, path)
                st.rerun()
            if c2.button("不通过", key=f"rev-fail-{row['key']}"):
                set_label(rows, row["key"], "fail", note, issue_value)
                save_review(rows, path)
                st.rerun()
            if c3.button("存疑", key=f"rev-unsure-{row['key']}"):
                set_label(rows, row["key"], "unsure", note, issue_value)
                save_review(rows, path)
                st.rerun()
            if c4.button("只存备注", key=f"rev-noteonly-{row['key']}"):
                set_label(rows, row["key"], human.get("label") or "unsure", note, issue_value)
                save_review(rows, path)
                st.rerun()
            if c5.button("清除", key=f"rev-clear-{row['key']}"):
                set_label(rows, row["key"], None)
                save_review(rows, path)
                st.rerun()

    st.download_button(
        "下载标注结果",
        data=path.read_text(encoding="utf-8"),
        file_name=path.name,
        mime="application/jsonl",
    )
    st.caption(f"共 {len(rows)} 条；标签取值：{' / '.join(LABELS)}")
