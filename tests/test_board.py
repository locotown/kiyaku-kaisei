"""理事会の検討資料と判断の記録のテスト。API は呼ばない。"""

import shutil

import pytest

from core.board import (BoardItem, BoardPaper, apply_to_draft, coverage, decisions_text, fix_tiers, status,
                        to_html)
from core.draft import Amendment, Draft

FINDING = {"article": "第47条", "topic_id": "1-1", "category": "必須", "issue": "i", "current_excerpt": "",
           "law_basis": ["第31条第1項"], "standard_basis": ["第47条"], "where": "規約", "proposal": "p"}
T1, T2, T3 = "法律の改正に合わせる変更", "暮らしや運営に関わる変更", "古い規定や表現の整理"


def make_draft():
    return Draft([
        Amendment("改正", "第47条", "第47条", "総会の会議及び議事", "第47条　…", "", ["1-1"], [], ["第47条"]),
        Amendment("改正", "第20条", "第20条", "区分所有者の責務", "第20条　…", "", ["10"], [], ["第20条"]),
        Amendment("改正", "第48条", "第48条", "議決事項", "第48条　…", "", ["other"], [], ["第48条"]),
        Amendment("改正", "第3条", "第3条", "使用者の資格", "第3条　…", "", ["other"], [], ["第18条"],
                  document="○○マンション駐車場使用細則"),
    ], "法的助言ではありません")


def item(title, arts, tier, options=None):
    return BoardItem(tier=tier, title=title, articles=arts, summary="", points=["p"], options=options or [], questions=[])


def make_paper():
    return BoardPaper(title="t", intro="", next_steps="", items=[
        item("責務", ["第20条"], T1),                                   # AI が誤って①にした → ②に直す
        item("総会", ["第47条"], T2, options=["x"]),                     # 必須の論点 → ①に直し、options は消す
        item("参照の整理", ["第48条"], T3),
        item("駐車場", ["駐車場使用細則 第3条"], T2, options=["採用", "見送り"]),
    ])


def test_fix_tiers_and_coverage():
    draft, paper = make_draft(), make_paper()
    fix_tiers(paper, draft)
    assert [(i.title, i.tier) for i in paper.items] == [("総会", T1), ("責務", T2), ("駐車場", T2), ("参照の整理", T3)]
    assert paper.items[0].options == []
    assert coverage(paper, draft) == []
    paper.items.pop()
    assert coverage(paper, draft) == ["第48条"]


def test_status_and_apply():
    draft, paper = make_draft(), make_paper()
    fix_tiers(paper, draft)
    d = {"0": {"decision": "理解した"}, "1": {"decision": "採用"}, "2": {"decision": "見送り"}}
    st = status(paper, d)
    assert not st["done"] and st["undecided"] == ["参照の整理"]
    d["3"] = {"decision": "確認した"}
    st = status(paper, d)
    assert st["done"] and st["skipped"] == ["駐車場"] and st["redraft"] == []
    applied = apply_to_draft(draft, paper, d)
    assert [a.article for a in applied.amendments] == ["第47条", "第20条", "第48条"]  # 見送りの細則の改定は除く
    d["1"] = {"decision": "修正して採用", "note": "努力義務にとどめる"}
    assert status(paper, d)["redraft"] == ["責務"]
    text = decisions_text(paper, d)
    assert "修正して採用" in text and "努力義務にとどめる" in text
    html = to_html(paper, d, "test")
    assert "理解する" in html and "判断する" in html and "確認する" in html and "見送り" in html


def test_explain_requires_board(monkeypatch):
    from fastapi.testclient import TestClient

    import app.main as M
    from app import store

    draft, paper = make_draft(), make_paper()
    fix_tiers(paper, draft)
    wid = store.new_id()
    d = store.path(wid)
    d.mkdir(parents=True)
    shutil.copy(M.SAMPLE, d / "source.txt")
    store.save(wid, {"name": "t", "info": {"型": "単棟型"}, "status": "検討資料あり", "articles": 87, "log": [],
                     "findings": [FINDING], "decisions": {"0": {"decision": "採用", "reason": ""}},
                     "draft": draft.to_dict(), "board": paper.model_dump(),
                     "board_decisions": {}})
    started = []
    monkeypatch.setattr(M, "_run_explain", lambda wid: started.append(wid))
    try:
        c = TestClient(M.app)
        assert c.post(f"/works/{wid}/explain", follow_redirects=False).status_code == 400  # 未判断
        form = {"b_decision_0": "理解した", "b_decision_1": "修正して採用", "b_note_1": "表現を和らげる",
                "b_decision_2": "採用", "b_decision_3": "確認した"}
        assert c.post(f"/works/{wid}/board/decisions", data=form, follow_redirects=False).status_code == 303
        r = c.post(f"/works/{wid}/explain", follow_redirects=False)
        assert r.status_code == 400 and "作り直して" in r.text  # 修正して採用 → 改定案の作り直しが先
        store.update(wid, draft_reflects_board=True)  # 作り直した後
        assert c.post(f"/works/{wid}/explain", follow_redirects=False).status_code == 303
        assert started == [wid]
        page = c.get(f"/works/{wid}").text
        assert "4. 理事会での検討" in page and "5. 住民向けの説明" in page
    finally:
        shutil.rmtree(d)


def test_items_without_articles_become_notes():
    draft, paper = make_draft(), make_paper()
    paper.items.append(item("関連条文の見直し", [], T2))
    fix_tiers(paper, draft)
    assert all(it.articles for it in paper.items)
    assert paper.notes and paper.notes[0].startswith("関連条文の見直し")
    assert "今回の改定案に含まれていない点" in to_html(paper)


CHOICES = [{"point": "届出の方法", "options": ["（ア）書面", "（イ）書面又は電磁的方法"], "note": "電磁的方法を使うかで選ぶ"}]


def draft_with_choice():
    d = make_draft()
    d.amendments[0] = Amendment("改正", "第47条", "第47条", "総会の会議及び議事", "第47条　…〔選択〕…", "", ["1-1"], [],
                                ["第47条"], choices=CHOICES)
    return d


def test_choice_points_any_tier_and_status():
    from core.board import choice_points, picked_text, remaining_choices

    draft, paper = draft_with_choice(), make_paper()
    fix_tiers(paper, draft)
    pts = choice_points(paper, draft)
    assert list(pts) == [0] and paper.items[0].tier == T1  # ①（必須）の議題でも選ぶ点として出す
    assert pts[0][0]["options"] == ["（ア）書面", "（イ）書面又は電磁的方法"]
    d = {"0": {"decision": "理解した"}, "1": {"decision": "採用"}, "2": {"decision": "採用"}, "3": {"decision": "確認した"}}
    st = status(paper, d, pts)
    assert not st["done"] and st["needs_choice"] == ["総会"]  # 案を選ぶまで判断済みにしない
    d["0"]["picked"] = {"0": "（イ）書面又は電磁的方法"}
    st = status(paper, d, pts)
    assert st["done"] and st["redraft"] == ["総会"]  # 選んだら作り直しが要る
    assert picked_text(pts[0], d["0"]["picked"]) == "第47条 届出の方法：（イ）書面又は電磁的方法"
    assert remaining_choices(draft) == ["第47条"]
    printed = to_html(paper, d, "t", pts)
    assert "選ぶ必要があります" in printed and "☑ （イ）書面又は電磁的方法" in printed and "□ （ア）書面" in printed
    # 見送りなら選ばなくてよい（②の議題に〔選択〕がある場合）
    draft.amendments[1] = Amendment("改正", "第20条", "第20条", "区分所有者の責務", "第20条　〔選択〕", "", ["10"], [], ["第20条"],
                                    choices=CHOICES)
    pts = choice_points(paper, draft)
    d2 = {**d, "1": {"decision": "見送り"}}
    assert "責務" not in status(paper, d2, pts)["needs_choice"]


def test_board_state_requires_choice_and_redraft(monkeypatch):
    from fastapi.testclient import TestClient

    import app.main as M
    from app import store

    draft, paper = draft_with_choice(), make_paper()
    fix_tiers(paper, draft)
    wid = store.new_id()
    d = store.path(wid)
    d.mkdir(parents=True)
    shutil.copy(M.SAMPLE, d / "source.txt")
    store.save(wid, {"name": "t", "info": {"型": "単棟型"}, "status": "検討資料あり", "articles": 87, "log": [],
                     "findings": [FINDING], "decisions": {"0": {"decision": "採用", "reason": ""}},
                     "draft": draft.to_dict(), "board": paper.model_dump(), "board_decisions": {}})
    monkeypatch.setattr(M, "_run_explain", lambda wid: None)
    try:
        c = TestClient(M.app)
        assert "選ぶ必要があります" in c.get(f"/works/{wid}").text
        form = {"b_decision_0": "理解した", "b_decision_1": "採用", "b_decision_2": "採用", "b_decision_3": "確認した"}
        c.post(f"/works/{wid}/board/decisions", data=form)
        st = M.board_state(store.load(wid))
        assert not st["ready"] and "案を選んでください" in st["reason"]
        c.post(f"/works/{wid}/board/decisions", data={**form, "b_pick_0_0": "（イ）書面又は電磁的方法"})
        w = store.load(wid)
        assert w["board_decisions"]["0"]["choice"] == "第47条 届出の方法：（イ）書面又は電磁的方法"
        st = M.board_state(w)
        assert not st["ready"] and st["needs_redraft"]
        assert c.post(f"/works/{wid}/explain", follow_redirects=False).status_code == 400
        # 作り直したが〔選択〕が残った場合も、住民向け説明には進めない
        store.update(wid, draft_reflects_board=True)
        st = M.board_state(store.load(wid))
        assert not st["ready"] and st["needs_redraft"] and "〔選択〕が残っています" in st["reason"]
        # 選んだ案で書き直された（〔選択〕がない）なら進める
        fixed = store.load(wid)["draft"]
        fixed["amendments"][0]["text"] = "第47条　…書面又は電磁的方法…"
        fixed["amendments"][0]["choices"] = []
        store.update(wid, draft=fixed)
        assert M.board_state(store.load(wid))["ready"]
    finally:
        shutil.rmtree(d)
