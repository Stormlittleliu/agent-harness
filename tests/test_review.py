# -*- coding: utf-8 -*-
"""复核流程：构建复核行、标注、汇总（不调用模型）。"""
import json

import pytest

from core.quality.review import (
    build_review,
    load_review,
    render_summary,
    save_review,
    set_label,
    summarize,
)


def _run_file(tmp_path):
    run = {
        "timestamp": "2026-11-03T23:00:00",
        "summary": {},
        "results": [
            {
                "id": "sb-rag-001", "kind": "retrieval", "cell": "单轮×检索", "trial": 0,
                "passed": True, "sources": ["故障排除.txt"], "mrr": 1.0,
            },
            {
                "id": "sb-multi-001", "kind": "multi_turn", "cell": "多轮×文本", "trial": 0,
                "passed": False, "answer": "建议重启", "tool_names": ["rag_summarize"],
                "coverage": 0.5, "tools_ok": True,
            },
        ],
    }
    path = tmp_path / "selfbuilt_demo.json"
    path.write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8")
    return path


def test_build_review_rows(tmp_path):
    rows = build_review(_run_file(tmp_path), use_judge=False)
    assert len(rows) == 2
    assert rows[0]["key"] == "sb-rag-001@0"
    assert rows[0]["auto"]["passed"] is True
    assert rows[1]["judge"] is None
    # 多轮任务的问题由台词拼起来
    assert "→" in rows[1]["question"]
    assert rows[1]["expected_points"] == ["充电触点"]


def test_review_roundtrip(tmp_path):
    rows = build_review(_run_file(tmp_path), use_judge=False)
    path = save_review(rows, tmp_path / "review.jsonl")
    loaded = load_review(path)
    assert loaded == rows


def test_set_label_and_summary(tmp_path):
    rows = build_review(_run_file(tmp_path), use_judge=False)
    assert set_label(rows, "sb-rag-001@0", "pass", "命中预期文档")
    assert set_label(rows, "sb-multi-001@0", "fail", "没有提到触点")
    report = summarize(rows)
    assert report["total"] == 2
    assert report["auto_pass"] == 1
    assert report["labeled"] == 2
    assert report["human_pass"] == 1
    assert report["unlabeled"] == 0


def test_set_label_stores_issue_and_note(tmp_path):
    rows = build_review(_run_file(tmp_path), use_judge=False)
    assert set_label(rows, "sb-rag-001@0", "fail", "召回的是 100 问，不是故障排除", "检索未召回")
    human = rows[0]["human"]
    assert human["issue"] == "检索未召回"
    assert "100 问" in human["note"]
    with pytest.raises(ValueError):
        set_label(rows, "sb-rag-001@0", "fail", "", "随便写的类型")


def test_set_label_rejects_bad_value(tmp_path):
    rows = build_review(_run_file(tmp_path), use_judge=False)
    with pytest.raises(ValueError):
        set_label(rows, "sb-rag-001@0", "maybe")


def test_set_label_clear(tmp_path):
    rows = build_review(_run_file(tmp_path), use_judge=False)
    set_label(rows, "sb-rag-001@0", "pass")
    assert set_label(rows, "sb-rag-001@0", None)
    assert rows[0]["human"] is None


def test_summary_detects_disagreements():
    rows = [
        {
            "key": "a@0", "auto": {"passed": True}, "judge": {"verdict": "fail"},
            "human": {"label": "fail"},
        },
        {
            "key": "b@0", "auto": {"passed": False}, "judge": {"verdict": "partial"},
            "human": {"label": "fail"},
        },
        {
            "key": "c@0", "auto": {"passed": False}, "judge": {"verdict": "pass"},
            "human": {"label": "unsure"},
        },
    ]
    report = summarize(rows)
    assert report["auto_vs_judge_disagreements"] == ["a@0", "c@0"]
    # a: 自动通过但人工判失败 -> 计入；b 三方一致；c 存疑不计
    assert report["auto_vs_human_disagreements"] == ["a@0"]


def test_render_summary_contains_counts():
    rows = [{"key": "a@0", "auto": {"passed": True}, "judge": {"verdict": "pass"}, "human": None}]
    text = render_summary(summarize(rows))
    assert "复核汇总" in text
    assert "总数：1" in text
