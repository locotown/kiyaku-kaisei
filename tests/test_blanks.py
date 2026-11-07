"""「○」の空欄の知らせ（計画D1）のテスト。API は呼ばない。"""

from core.blanks import BLANK, in_blocks, in_draft, snippets
from core.consolidate import Block
from tests.test_partial import FORM, board_work  # noqa: F401  (pytest の fixture)


def test_snippets_show_where_the_blank_is():
    text = ("第35条　管理組合に次の役員を置く。\n二　副理事長　○名\n三　理事（理事長を含む。）　○名\n"
            "2　理事長、副理事長及び会計担当理事は、理事のうちから、理事会で選任し、任期は○年とする。")
    got = snippets(text)
    assert got[0] == "二 副理事長 ○名" and got[1] == "三 理事（理事長を含む。） ○名"   # 短い行は行ごと
    assert got[2].startswith("…") and "任期は○年" in got[2]
    assert snippets("この規約は、○○マンションの管理について定める。") and not snippets("第35条　理事　5名")


def test_kanji_zero_inside_numbers_is_not_a_blank():
    assert not BLANK.search("二〇二六年") and BLANK.search("令和〇年〇月〇日") and BLANK.search("◯◯マンション")


def test_in_draft_skips_deleted_articles_and_names_documents():
    draft = {"amendments": [
        {"kind": "改正", "article": "第52条", "text": "第52条　理事が○分の1以上の理事の同意を得て…"},
        {"kind": "削除", "article": "第53条", "text": "第53条　○日以内"},
        {"kind": "改正", "article": "第3条", "document": "総会運営細則", "text": "第3条　○日前までに通知する。"},
        {"kind": "改正", "article": "第60条", "text": "第60条　年利5%の遅延損害金"},
    ]}
    assert [x["where"] for x in in_draft(draft)] == ["第52条", "総会運営細則 第3条"]
    assert in_draft(None) == []


def test_in_blocks_names_article_and_marks_amended_ones():
    blocks = [Block("title", ["○○マンション管理規約"]),
              Block("article", ["（役員）", "第35条　管理組合に次の役員を置く。", "二　副理事長　○名"], "改正"),
              Block("article", ["（会計年度）", "第56条　会計年度は、毎年○月○日から翌年○月○日までとする。"]),
              Block("article", ["（目的）", "第1条　この規約は、管理について定める。"])]
    got = in_blocks(blocks)
    assert [(x["where"], x["changed"]) for x in got] == [("第35条（役員）", True), ("第56条（会計年度）", False)]


def test_step3_tells_blanks_in_draft(board_work):
    """改定案の条に「○」が残っていれば、ステップ3の「理事会の前に、人が確かめること」で条と箇所を知らせ、「条の文を直す」へ案内する。"""
    M, store, c, wid, _, _ = board_work
    w = store.load(wid)
    page = c.get(f"/works/{wid}").text
    assert "「○」の空欄が残っている条" not in page
    w["draft"]["amendments"][0]["text"] += "\n2　理事長は、○か月に1回以上、職務の執行の状況を理事会に報告しなければならない。"
    store.update(wid, draft=w["draft"])
    page = c.get(f"/works/{wid}").text
    assert "「○」の空欄が残っている条があります（1条）" in page and "○か月に1回" in page and "/articles#row-top" in page


def test_step6_tells_blanks_in_latest_rules(board_work, monkeypatch):
    """最新の規約に「○」が残っていれば、ステップ6で一覧を出し、今回の改定で入った条とそれ以外で、入れる数字の出どころを分けて案内する。"""
    M, store, c, wid, _, _ = board_work
    finals = [{"n": 0, "doc": "規約", "title": "t", "blocks": [], "left": [], "count": 1, "history": "h", "variants": [],
               "blanks": [{"where": "第35条（役員）", "snippets": ["二 副理事長 ○名"], "changed": True},
                          {"where": "第56条（会計年度）", "snippets": ["…毎年○月○日から…"], "changed": False}]}]
    monkeypatch.setattr(M, "final_documents", lambda work_id, work: finals)
    store.update(wid, meeting={"results": {"規約": "可決"}, "date": "2026-05-24", "name": "第10回通常総会"})
    page = c.get(f"/works/{wid}").text
    assert "「○」の空欄が残っている箇所があります（2か所）" in page
    assert "今回の改定で入った条（第35条（役員））は理事会・総会で決めた数字を" in page and "今お使いの規約（原本）の数字" in page


def test_check_draft_warns_new_blanks_only():
    """改定案の検査（AI が使う check_draft）：標準管理規約から写した新しい「○」は注意に出す。今の規約にもともとある「○」は出さない。"""
    from pathlib import Path

    from core.draft import check
    from core.ingest import load_kiyaku
    from tests.test_draft import amendment

    k = load_kiyaku(Path(__file__).resolve().parents[1] / "evals/data/r7_tantou_before.txt")
    f = []
    base = amendment(k)
    _, _, warn = check({"amendments": [base], "notes": "法的助言ではありません"}, k, f or [])
    assert not any("「○」の空欄" in w for w in warn)
    added = dict(base, text=base["text"] + "\n9　理事長は、○か月に1回以上、報告しなければならない。")
    _, _, warn = check({"amendments": [added], "notes": "法的助言ではありません"}, k, f or [])
    assert any("「○」の空欄が残っています" in w and "○か月に1回" in w for w in warn)
