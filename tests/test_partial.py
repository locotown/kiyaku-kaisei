"""理事会の判断を、対象の条だけに反映する作り直し（core/partial.py と app/main.py の _run_partial）のテスト。API は呼ばない。"""

import shutil

import pytest

from core import partial
from core.board import fix_tiers
from core.draft import Amendment, Draft
from tests.test_board import FINDING, draft_with_choice, make_paper

FORM = {"b_decision_0": "理解した", "b_decision_1": "採用", "b_decision_2": "採用", "b_decision_3": "確認した",
        "b_q_0": "（イ）書面又は電磁的方法"}


def fake_rewrite(text="第47条　…書面又は電磁的方法…"):
    out = partial.RewriteOut(
        amendments=[
            partial.AmendmentOut(document="規約", article="第47条", caption="総会の会議及び議事", text=text, reason="理事会で選んだ案にしました。",
                                 finding_refs=["1-1"], law_basis=[], standard_basis=["第47条"], choices=[]),
            # 対象でない条を AI が返しても、使わない
            partial.AmendmentOut(document="規約", article="第48条", caption="議決事項", text="第48条　勝手に変えた文", reason="",
                                 finding_refs=["other"], law_basis=[], standard_basis=["第48条"], choices=[]),
        ],
        notes="【組合が選ぶ点】選び終わりました。総会提案の下書きであり、法的助言ではありません。",
        summary="第47条の届出の方法を、理事会で選んだ「書面又は電磁的方法」にしました。",
        others=[partial.OtherRef(ref="第48条", why="第47条の届出の方法を参照しているため")])
    return lambda material, effort="high": (out, 0.12)


def fake_check(verdict="気になる点あり"):
    """確かめる役の呼び出し（_call）だけを偽物にする。根拠のない指摘を落とす処理は本物を通す。"""
    out = partial.CheckOut(verdict=verdict, summary="理事会の判断どおりです。", concerns=[
        partial.Concern(kind="要確認", ref="第47条", point="根拠のない指摘", basis="", suggestion="")])
    return lambda system, material, ask, fmt, effort: (out, {"input_tokens": 1000, "output_tokens": 500})


@pytest.fixture
def board_work(monkeypatch):
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
    c = TestClient(M.app)
    c.post(f"/works/{wid}/board/decisions", data=FORM)
    started = []
    real = M._run_partial
    monkeypatch.setattr(M, "_run_partial", lambda w: started.append(w))
    try:
        yield M, store, c, wid, started, real
    finally:
        shutil.rmtree(d)


def test_targets_and_buttons(board_work):
    M, store, c, wid, started, _ = board_work
    w = store.load(wid)
    assert M.board_state(w)["needs_redraft"]
    assert M.redraft_targets(w)["refs"] == ["第47条"]           # 案を選んだ議題の条だけ
    page = c.get(f"/works/{wid}").text
    assert "対象の条だけ作り直す" in page and "作り直す条：<b>第47条</b>" in page and "全体を作り直す" in page
    assert c.post(f"/works/{wid}/board/redraft", data={"mode": "partial"}, follow_redirects=False).status_code == 303
    w = store.load(wid)
    assert started == [wid] and w["status"] == "改定案作成中" and w["draft_mode"] == "partial"
    view = M.progress_view(w)
    assert view["steps"] == ["対象の条を読む", "対象の条を書き直す", "直した条を確かめる"] and view["estimate"] == "2〜5分"
    assert "理事会の判断を、対象の条に反映しています" in c.get(f"/works/{wid}").text


def test_partial_rewrites_only_targets(board_work, monkeypatch):
    M, store, c, wid, _, run = board_work
    monkeypatch.setattr(partial, "rewrite", fake_rewrite())
    monkeypatch.setattr(partial, "_call", fake_check())
    before = store.load(wid)["draft"]
    store.update(wid, status="改定案作成中", draft_mode="partial")
    run(wid)
    w = store.load(wid)
    assert w["status"] == "改定案あり", w["log"][-3:]
    am = {a["article"]: a for a in w["draft"]["amendments"]}
    assert am["第47条"]["text"] == "第47条　…書面又は電磁的方法…" and am["第47条"]["choices"] == [], w.get("draft_partial")
    assert am["第48条"] == next(a for a in before["amendments"] if a["article"] == "第48条")   # 対象でない条はそのまま
    assert w["draft"]["notes"].startswith("【組合が選ぶ点】")
    pr = w["draft_partial"]
    # 根拠のない指摘は落とし、残らなければ「問題なし」にする
    assert pr["status"] == "済み" and pr["changed"] == ["第47条"] and pr["check"]["verdict"] == "問題なし" and pr["check"]["concerns"] == []
    assert pr["cost_usd"] > 0.12 and "部分的な作り直し" in w["costs"][-1]["step"]
    assert M.board_state(w)["ready"]                           # 〔選択〕が外れ、住民向け説明に進める
    page = c.get(f"/works/{wid}").text
    assert "対象の条だけ作り直しました" in page and "ほかの条も直す必要がありそうです" in page
    assert "第47条の届出の方法を参照しているため" in page


def test_partial_failure_keeps_draft(board_work, monkeypatch):
    M, store, c, wid, _, run = board_work

    def boom(material, effort="high"):
        raise RuntimeError("通信が切れました")
    monkeypatch.setattr(partial, "rewrite", boom)
    before = store.load(wid)["draft"]
    store.update(wid, status="改定案作成中", draft_mode="partial")
    run(wid)
    w = store.load(wid)
    assert w["status"] == "改定案あり" and w["draft"] == before and w["draft_partial"]["status"] == "失敗"
    page = c.get(f"/works/{wid}").text
    assert "うまくいきませんでした" in page and "今の改定案はそのまま残っています" in page


def test_partial_rejects_draft_that_fails_the_check(board_work, monkeypatch):
    """書き直した改定案が機械的な検査に通らなければ、反映しない。"""
    M, store, c, wid, _, run = board_work
    monkeypatch.setattr(partial, "rewrite", fake_rewrite(text=""))   # 改正の条の本文が空
    monkeypatch.setattr(partial, "_call", fake_check())
    before = store.load(wid)["draft"]
    store.update(wid, status="改定案作成中", draft_mode="partial")
    run(wid)
    w = store.load(wid)
    assert w["draft"] == before and w["draft_partial"]["status"] == "失敗" and "検査" in w["draft_partial"]["error"]


def test_partial_updates_human_edit(board_work, monkeypatch):
    """委員会が手で直した条を書き直したら、直した文も新しい文にする（作り直しで古い文に戻さない）。"""
    M, store, c, wid, _, run = board_work
    store.update(wid, human_edits={"規約|第47条": {"text": "第47条　委員会の文〔選択〕", "original": "第47条　…〔選択〕…",
                                                   "note": "会議で直した", "review": {"status": "済み"}}})
    monkeypatch.setattr(partial, "rewrite", fake_rewrite())
    monkeypatch.setattr(partial, "_call", fake_check())
    store.update(wid, status="改定案作成中", draft_mode="partial")
    run(wid)
    e = store.load(wid)["human_edits"]["規約|第47条"]
    assert e["text"] == "第47条　…書面又は電磁的方法…" and "review" not in e and "理事会の判断を反映" in e["note"]


def test_recover_keeps_draft_when_partial_interrupted(board_work):
    M, store, c, wid, _, _ = board_work
    store.update(wid, status="改定案作成中", draft_mode="partial")
    M.recover_interrupted()
    w = store.load(wid)
    assert w["status"] == "改定案あり" and w["draft_partial"]["status"] == "中断"


def test_referencing_and_merge():
    d = Draft([Amendment("改正", "第47条", "第47条", "c", "第47条　…", "", [], [], []),
               Amendment("改正", "第48条", "第48条", "c", "第48条　第47条の定めにより…", "", [], [], []),
               Amendment("改正", "第3条", "第3条", "c", "第3条　第47条…", "", [], [], [], document="細則")], "n")
    assert [a.article for a in partial.referencing(d, [d.amendments[0]])] == ["第48条"]   # 別の文書の同じ番号は数えない
    out = partial.RewriteOut(amendments=[partial.AmendmentOut(document="規約", article="第47条", caption="c", text="第47条　新",
                                                              reason="r", finding_refs=[], law_basis=[], standard_basis=[], choices=[])],
                             notes="", summary="s")
    new, changed = partial.merge(d, out, [d.amendments[0]])
    assert new.amendments[0].text == "第47条　新" and new.notes == "n" and len(changed) == 1


def test_full_redraft_paths_set_mode(board_work, monkeypatch):
    """「全体を作り直す」と、ステップ3の「最初から作り直す」（mode を送らない）は全体の作り直しになり、前の部分的な結果を出さない。"""
    M, store, c, wid, _, _ = board_work
    calls = []
    monkeypatch.setattr(M, "_run_draft", lambda *a, **k: calls.append(a))
    store.update(wid, draft_mode="partial", draft_partial={"status": "済み", "at": "x", "targets": ["第47条"], "summary": "前の結果"})
    assert c.post(f"/works/{wid}/board/redraft", follow_redirects=False).status_code == 303   # mode なし
    w = store.load(wid)
    assert calls == [(wid, True)] and w["draft_mode"] == "full"
    store.update(wid, status="改定案あり")
    assert "前の結果" not in c.get(f"/works/{wid}").text
    store.update(wid, status="検討資料あり", draft_mode="partial")
    c.post(f"/works/{wid}/draft", follow_redirects=False)   # ステップ3の「改定案を作り直す」
    assert store.load(wid)["draft_mode"] == "full"
