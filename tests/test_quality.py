"""改定案の確認結果の表示のテスト。"""

from core.quality import RUBRIC_PLAIN, draft_quality
from core.drafting import RUBRIC


def test_quality():
    work = {"draft": {"amendments": [{"document": "規約"}, {"document": "規約", "choices": ["ア", "イ"]},
                                     {"document": "○○マンション総会運営細則"}]},
            "draft_errors": [],
            "draft_evaluations": [{"result": "needs_revision", "explanation": "x"},
                                  {"result": "satisfied", "explanation": "An independent grader found all criteria met:\n- 項目 (met): ok"}]}
    q = draft_quality(work)
    assert q["level"] == "ok" and "2回目で合格" in q["head"] and q["checks_ok"]
    assert [r["result"] for r in q["rounds"]] == ["直しが必要", "合格"]
    assert q["rounds"][1]["explanation"].startswith("採点役のまとめ") and "（満たす）" in q["rounds"][1]["explanation"]
    assert q["by_doc"] == {"規約": 2, "○○マンション総会運営細則": 1} and q["choices"] == 1
    assert draft_quality({**work, "draft_evaluations": [{"result": "max_iterations_reached"}]})["level"] == "warn"
    assert draft_quality({**work, "draft_evaluations": []})["level"] == "warn"


def test_rubric_plain_matches_rubric():
    # 採点役の確認項目を変えたら、画面向けの言い換えも合わせて直す
    import re

    assert len(RUBRIC_PLAIN) == sum(1 for line in RUBRIC.splitlines() if re.match(r"^\d+\. ", line))


def test_parse_explanation_and_extra():
    from core.quality import parse_explanation

    text = ("An independent grader found all criteria met:\n- 改定案（kaitei.json）がルーブリック各項目を満たしているか (met): "
            "私の環境では get_articles などの取得ツールが使えないため、現行規約の原文との一字一句の照合はできていません。\n\n"
            "(1) /mnt/session/outputs/kaitei.json は存在し、{amendments:[5件], notes} の形の JSON です。\n"
            "(2) 必須の論点はすべて finding_refs に含まれ、条文で解消されています。\n"
            "(7) すべての改定に law_basis と standard_basis があります。\n")
    p = parse_explanation(text)
    assert p["items"][2] == "必須の論点はすべて対応する指摘の欄に含まれ、条文で解消されています。"
    assert p["items"][7] == "すべての改定に根拠（区分所有法と標準管理規約）があります。"
    assert "改定 5件と申し送り" in p["items"][1]
    assert len(p["limits"]) == 1 and "一字一句の照合はできていません" in p["limits"][0] and "get_articles" not in p["limits"][0]

    work = {"draft": {"amendments": [{"document": "規約", "article": "第49条", "kind": "改正"},
                                     {"document": "規約", "article": "第69条", "kind": "改正"},
                                     {"document": "規約", "article": "第25条の2", "kind": "新設"}]},
            "findings": [{"document": "規約", "article": "第49条"}, {"document": "規約", "article": "規定なし"}],
            "decisions": {"0": {"decision": "採用"}, "1": {"decision": "採用"}},
            "draft_evaluations": [{"result": "satisfied", "explanation": text}]}
    q = draft_quality(work)
    assert q["extra"] == ["第69条"] and q["limits"] and q["checklist"][1]["ok"] and q["checklist"][1]["note"]


def test_current_texts_for_grader():
    from core.corpus import Corpus
    from core.drafting import current_texts
    from core.findings import Finding
    from core.ingest import load_collection

    from core.config import ROOT

    corpus = Corpus.from_collection(load_collection(ROOT / "evals/data/old_collection.txt"))
    f = lambda doc, art: Finding(art, "1-1", "必須", "", "", [], [], "規約", "", document=doc)
    t = current_texts(corpus, [f("規約", "第49条"), f("規約", "第49条"), f("○○マンションペット飼育細則", "1."), f("規約", "規定なし")])
    assert t.count("■ 規約 第49条") == 1 and "組合員総数の4分の3以上" in t
    assert "■ ○○マンションペット飼育細則 1." in t
    assert not [line for line in t.splitlines() if line[:2].rstrip(".").isdigit() and line[1:3].startswith(". ")]  # 行頭に「1. 」が出ない


def test_source_notes(monkeypatch):
    import shutil

    from fastapi.testclient import TestClient

    import app.main as M
    from app import store
    from core.quality import source_kind

    assert source_kind(".docx") == "電子データ" and source_kind(".pdf") == "PDF" and source_kind(".txt", sample=True) == "サンプル"
    monkeypatch.setattr(M, "_run_review", lambda wid: None)
    c = TestClient(M.app)
    # 文字を読み取れない PDF（ここでは条のないテキストを .pdf 名で送る代わりに、条のないテキストで確かめる）
    r = c.post("/works", data={"name": "t"}, files={"file": ("x.txt", "規約\\nなにもない".encode(), "text/plain")})
    assert r.status_code == 400 and "スキャン" not in r.text
    wid = store.new_id()
    d = store.path(wid)
    d.mkdir(parents=True)
    shutil.copy(M.SAMPLES["docx"]["path"], d / "source.docx")
    store.save(wid, {"name": "うちの規約", "info": {"型": "単棟型"}, "status": "点検済み", "articles": 74, "log": [],
                     "documents": [{"kind": "規約", "title": "a", "articles": 74, "style": "条", "annotations": 0},
                                   {"kind": "細則", "title": "b", "articles": 3, "style": "条", "annotations": 0}]})
    try:
        page = c.get(f"/works/{wid}").text
        assert "Wordから読み込みました" in page and "最新版か" in page
    finally:
        shutil.rmtree(d)


def test_timeout_is_shown_before_grader_result():
    from core.quality import draft_quality

    work = {"draft": {"amendments": []}, "draft_stop": "timeout", "draft_plan": {"deadline_min": 30},
            "draft_evaluations": [{"result": "satisfied", "explanation": ""}]}
    q = draft_quality(work)
    assert q["level"] == "warn" and q["stopped"] and "時間の上限（30分）" in q["head"]


def test_cost_history_keeps_redraft():
    from core.quality import cost_lines

    work = {"costs": [{"step": "点検", "cost": {"amount": "77"}}, {"step": "改定案", "cost": {"amount": "537"}},
                      {"step": "改定案の作り直し", "cost": {"amount": "340"}}]}
    c = cost_lines(work)
    assert [x["step"] for x in c["lines"]] == ["点検", "改定案", "改定案の作り直し"] and c["total"] == 9.54
    # 記録を残す前の作業は、最後の値だけ
    assert cost_lines({"review_cost": {"amount": "100"}, "draft_cost": {"amount": "250"}})["total"] == 3.5
