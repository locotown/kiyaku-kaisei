"""想定ユーザー3人（スマホの理事長・Mac の委員・スマホの新任理事）で通しで使って見つかった問題の、直したところのテスト。API は呼ばない。"""

from core import board as B
from core.board import BoardItem, BoardPaper, fix_tiers
from core.draft import Amendment, Draft
from core.taisho import to_html
from tests.test_board import T1, T2
from tests.test_partial import board_work  # noqa: F401  (pytest の fixture)


def mixed_draft():
    """第45条に、必須の論点（2-1）と推奨の論点（5：国内管理人）が同じ条に入っている改定案。"""
    return Draft([
        Amendment("改正", "第45条", "第45条", "招集手続", "第45条　…", "", ["2-1", "5"], [], ["第43条"]),
        Amendment("新設", "第33条の2", None, "国内管理人", "第33条の2　…", "", ["5"], [], ["第31条の3"]),
    ], "法的助言ではありません")


def test_tier_follows_item_topics_not_shared_article():
    """推奨の論点の議題は、必須の変更と同じ条に入っていても①（変えないことはできない）にしない。"""
    paper = BoardPaper(title="t", intro="", next_steps="", items=[
        BoardItem(tier=T1, title="招集通知", articles=["第45条"], summary="", points=["p"], options=[], questions=[], finding_refs=["2-1"]),
        BoardItem(tier=T1, title="国内管理人", articles=["第33条の2", "第45条"], summary="", points=["p"], options=[], questions=[],
                  finding_refs=["5"]),
    ])
    fix_tiers(paper, mixed_draft())
    assert [(i.title, i.tier) for i in paper.items] == [("招集通知", T1), ("国内管理人", T2)]


def test_skip_keeps_article_with_required_change_and_asks_partial_redraft():
    """②を見送っても、必須の変更が入っている条は消さず、見送った部分だけを作り直しで取り除く。"""
    draft = mixed_draft()
    paper = BoardPaper(title="t", intro="", next_steps="", items=[
        BoardItem(tier=T1, title="招集通知", articles=["第45条"], summary="", points=["p"], options=[], questions=[], finding_refs=["2-1"]),
        BoardItem(tier=T2, title="国内管理人", articles=["第33条の2", "第45条"], summary="", points=["p"], options=[], questions=[],
                  finding_refs=["5"]),
    ])
    decisions = {"0": {"decision": "理解した"}, "1": {"decision": "見送り"}}
    assert B.skipped_refs(paper, decisions, draft) == {"第33条の2"}
    assert [a.article for a in B.apply_to_draft(draft, paper, decisions).amendments] == ["第45条"]
    st = B.status(paper, decisions, {}, draft)
    assert "国内管理人" in st["redraft"] and "国内管理人" in st["skipped"]
    assert "論点：5" in B.decisions_text(paper, decisions)


def test_taisho_marks_skipped_rows_and_committee_note():
    """理事会で見送りにした条は、行の番号を変えずに印を付ける。委員会で直した条は、直した点を理由の欄に添える。"""
    from app.main import SAMPLE
    from core.corpus import Corpus
    from core.ingest import load_kiyaku

    corpus = Corpus(load_kiyaku(SAMPLE))
    draft = Draft([Amendment("改正", "第47条", "第47条", "総会の会議及び議事", "第47条　委員会で直した文", "AI の理由", ["1-1"], [], []),
                   Amendment("改正", "第20条", "第20条", "区分所有者の責務", "第20条　…", "", ["10"], [], [])], "n")
    edits = {"規約|第47条": {"text": "第47条　委員会で直した文", "original": "第47条　…", "note": "会議で言い回しを平易にした"}}
    page = to_html(draft, corpus, edits=edits, skipped={"第20条"})
    assert "理事会で見送り（総会には出しません）" in page and "1条は理事会で見送りにした" in page
    assert "委員会で直した点：</b>会議で言い回しを平易にした" in page
    assert page.index("行1") < page.index("行2")                     # 行の番号はそのまま


def test_board_prompt_tells_ai_about_committee_edits():
    draft = mixed_draft()
    edits = {"規約|第45条": {"text": "第45条　…", "note": "会議で直した"}}
    p = B.build_prompt(draft, {"型": "単棟型"}, edits)
    assert "committee_edit" in p and "会議で直した" in p and "必須の論点ID" in p
    from core.explain import build_prompt as explain_prompt
    e = explain_prompt(draft, {"型": "単棟型"}, board="- メモ：次回確認", edits=edits)
    assert "committee_edit" in e and "理事会の段取りや宿題は書かない" in e


def test_ai_buttons_confirm_cost_and_time(board_work):
    """AI を動かすボタンは、時間と費用の目安を確かめてから動かす。"""
    M, store, c, wid, _, _ = board_work
    page = c.get(f"/works/{wid}").text
    assert 'data-ai="対象の条（第47条）だけを作り直します' in page
    assert "AI の利用料（APIキー）として請求されます" in page and "window.confirm(b.dataset.ai)" in page
    assert "改定案は 約" not in page or "AI の費用" in page


def test_costs_include_board_explain_and_photos(board_work, monkeypatch):
    """検討資料・住民向け説明・写真の読み取りの費用も、合計に入れる。"""
    M, store, c, wid, _, _ = board_work
    import core.board as cb
    import core.explain as ce

    paper = M._board(store.load(wid))
    monkeypatch.setattr(cb, "generate", lambda d, info, edits=None: (paper, {"input_tokens": 10000, "output_tokens": 2000}))
    M._run_board(wid)
    w = store.load(wid)
    assert w["costs"][-1]["step"] == "理事会の検討資料"
    store.update(wid, notes=[{"id": "b1", "at": "x", "photos": [{}, {}], "cost_usd": 0.12, "proposals": []}])
    from core.quality import cost_lines

    lines = cost_lines(store.load(wid))["lines"]
    assert any(x["step"] == "書き込みの読み取り（写真2枚）" for x in lines)
    page = c.get(f"/works/{wid}").text
    assert "AI の費用：これまで 約$" in page
    del ce


def test_progress_hides_english_only_ai_notes(board_work):
    M, store, c, wid, _, _ = board_work
    store.update(wid, status="改定案作成中", draft_mode="full")
    store.append_log(wid, "message", "Now the law articles.")
    store.append_log(wid, "message", "条文を確かめます")
    texts = [l["text"] for l in M.progress_view(store.load(wid))["lines"]]
    assert "条文を確かめます" in texts and not any("Now the law" in t for t in texts)


def test_legend_and_status_after_meeting(board_work):
    M, store, c, wid, _, _ = board_work
    store.update(wid, status="説明文あり", meeting={"results": {"規約": "可決"}})
    page = c.get(f"/works/{wid}").text
    assert "＝人が決め終えた（エラーではありません）" in page and "状態：<b id=\"status\">総会の結果あり</b>" in page


def test_work_list_shows_created_time(board_work):
    M, store, c, wid, _, _ = board_work
    page = c.get("/").text
    ts = wid[:13]
    assert f"{int(ts[4:6])}/{int(ts[6:8])} {ts[9:11]}:{ts[11:13]}" in page


def test_skipped_mark_keeps_articles_with_required_change(board_work):
    """新旧対照表の「見送り」の印は、必須の変更も入っていて総会に出す条には付けない（作業の画面から作る印で確かめる）。"""
    M, store, c, wid, _, _ = board_work
    draft = mixed_draft()
    paper = BoardPaper(title="t", intro="", next_steps="", items=[
        BoardItem(tier=T1, title="招集通知", articles=["第45条"], summary="", points=["p"], options=[], questions=[], finding_refs=["2-1"]),
        BoardItem(tier=T2, title="国内管理人", articles=["第33条の2", "第45条"], summary="", points=["p"], options=[], questions=[],
                  finding_refs=["5"]),
    ])
    store.update(wid, draft=draft.to_dict(), board=paper.model_dump(),
                 board_decisions={"0": {"decision": "理解した"}, "1": {"decision": "見送り"}})
    assert M._skipped(store.load(wid)) == {"第33条の2"}


def _mixed_work(store, wid):
    """必須（2-1）と推奨（5）が同じ第45条に入る改定案と、その2つの議題（3回目の確認の場面）。"""
    draft = mixed_draft()
    paper = BoardPaper(title="t", intro="", next_steps="", items=[
        BoardItem(tier=T1, title="招集通知", articles=["第45条"], summary="", points=["p"], options=[], questions=[], finding_refs=["2-1"]),
        BoardItem(tier=T2, title="国内管理人", articles=["第33条の2", "第45条"], summary="", points=["p"], options=[], questions=[],
                  finding_refs=["5"]),
    ])
    store.update(wid, draft=draft.to_dict(), board=paper.model_dump(), draft_reflects_board=True,
                 board_decisions={"0": {"decision": "理解した"}, "1": {"decision": "見送り",
                                  "history": [{"at": "x", "from": "", "to": "見送り"}]}})


def test_toggle_skip_after_redraft_asks_for_redraft_again(board_work):
    """一度作り直したあとで「見送り」を「採用」に戻したら、作り直しの案内が出て、必須と同じ条が対象になる。"""
    M, store, c, wid, _, _ = board_work
    _mixed_work(store, wid)
    store.update(wid, board_applied=M._board_snapshot(store.load(wid)["board_decisions"]))  # 見送りで作り直した記録
    c.post(f"/works/{wid}/board/decisions", data={"b_decision_0": "理解した", "b_decision_1": "採用"})
    w = store.load(wid)
    st = M.board_state(w)
    assert st["needs_redraft"] and "第45条" in M.redraft_targets(w)["refs"]


def test_board_change_after_meeting_is_flagged(board_work):
    """総会の結果を記録したあとで理事会の判断を変えたら、黙って書き換えず印を付ける。"""
    M, store, c, wid, _, _ = board_work
    _mixed_work(store, wid)
    store.update(wid, meeting={"results": {"規約": "可決"}}, explain={"title": "t", "items": []}, explain_metrics={})
    c.post(f"/works/{wid}/board/decisions", data={"b_decision_0": "理解した", "b_decision_1": "採用"})
    w = store.load(wid)
    assert w.get("board_changed_after_meeting") and w.get("explain_stale")


def test_empty_meeting_save_keeps_previous_results(board_work):
    M, store, c, wid, _, _ = board_work
    store.update(wid, meeting={"results": {"規約": "可決"}, "name": "総会"})
    c.post(f"/works/{wid}/meeting", data={"m_name": "総会"})
    assert store.load(wid)["meeting"]["results"] == {"規約": "可決"}


def test_applied_items_are_not_redrafted_again(board_work):
    """前の作り直しで反映した議題は、判断・メモが変わっていなければ、次の作り直しの対象にしない。"""
    M, store, c, wid, _, _ = board_work
    _mixed_work(store, wid)
    d = store.load(wid)["board_decisions"]
    d["1"] = {"decision": "修正して採用", "note": "言い回しを平易に", "choice": ""}
    store.update(wid, board_decisions=d, draft_reflects_board=False)
    assert "国内管理人" in M.redraft_targets(store.load(wid))["items"]
    store.update(wid, board_applied=M._board_snapshot(d))
    assert "国内管理人" not in M.redraft_targets(store.load(wid))["items"]


def test_article_edit_after_meeting_is_flagged(board_work):
    M, store, c, wid, _, _ = board_work
    store.update(wid, meeting={"results": {"規約": "可決"}})
    M._edit_articles(wid, [{"document": "規約", "article": "第47条", "text": "第47条　総会のあとで直した文", "note": ""}], "log")
    assert store.load(wid).get("board_changed_after_meeting")


def test_reverting_a_decision_clears_the_redraft(board_work):
    """判断を変えてから元に戻したら、作り直しは要らない（戻しただけで AI の費用を求めない。4回目の確認で分かった）。"""
    M, store, c, wid, _, _ = board_work
    _mixed_work(store, wid)
    d = store.load(wid)["board_decisions"]
    store.update(wid, board_applied=M._board_snapshot(d))
    c.post(f"/works/{wid}/board/decisions", data={"b_decision_0": "理解した", "b_decision_1": "採用"})
    assert M.board_state(store.load(wid))["needs_redraft"]
    c.post(f"/works/{wid}/board/decisions", data={"b_decision_0": "理解した", "b_decision_1": "見送り"})
    w = store.load(wid)
    assert not M.board_state(w)["needs_redraft"] and w["draft_reflects_board"]


def test_journey_follows_stale_steps(board_work):
    """判断が変わって説明が古くなったら、上の「次にすること」も説明のステップを案内する（「すべて済み」にしない）。"""
    M, store, c, wid, _, _ = board_work
    w = store.load(wid)
    w.update(explain={"title": "t", "items": []}, explain_stale=True, board_decisions={
        str(i): {"decision": "理解した" if it["tier"] == T1 else "採用"} for i, it in enumerate(w["board"]["items"])})
    j = M.journey(w, {"ready": True})
    assert j["current"] in ("explain", "board", "draft") and "すべての段階が済みました" not in j["next"]


def test_backfill_applied_record_for_older_works(board_work):
    """反映の記録がない（前に作り直した）作業でも、判断を変える前の判断を反映済みとして補う。"""
    M, store, c, wid, _, _ = board_work
    _mixed_work(store, wid)
    store.update(wid, board_applied=None)
    c.post(f"/works/{wid}/board/decisions", data={"b_decision_0": "理解した", "b_decision_1": "採用"})
    c.post(f"/works/{wid}/board/decisions", data={"b_decision_0": "理解した", "b_decision_1": "見送り"})
    w = store.load(wid)
    assert w["board_applied"] and not M.board_state(w)["needs_redraft"]


def test_edits_normalize_newlines_and_mark_explain_stale(board_work):
    M, store, c, wid, _, _ = board_work
    store.update(wid, explain={"title": "t", "items": []})
    M._edit_articles(wid, [{"document": "規約", "article": "第47条", "text": "第47条　一\r\n2　二", "note": ""}], "log")
    w = store.load(wid)
    assert "\r" not in w["draft"]["amendments"][0]["text"] and w.get("explain_stale")


def test_display_status_comes_from_data():
    """状態の表示は中身から決める（作り直しで「改定案あり」に戻っても、説明・総会の結果があれば後の段階を出す）。"""
    from app.store import display_status

    base = {"status": "改定案あり", "draft": {"amendments": []}}
    assert display_status(base | {"explain": {"title": "t"}}) == "説明文あり"
    assert display_status(base | {"explain": {"title": "t"}, "meeting": {"results": {"規約": "可決"}}}) == "総会の結果あり"
    assert display_status(base | {"status": "説明文作成中", "explain": {"title": "t"}}) == "説明文作成中"


def test_diff_ignores_line_break_differences():
    """改行の形（空行・\\r\\n）だけの違いは、提案の「変わるところ」に出さない。"""
    from core.notes import changes

    cur = "第1条　一\n\n2　二\n\n3　三"
    assert changes(cur, "第1条　一\r\n2　二\n3　三") == []
    assert len(changes(cur, "第1条　一\n2　二を直した\n3　三")) == 1


def test_old_slash_joined_notes_are_split_by_date():
    from core.taisho import edit_note

    a = Amendment("改正", "第38条の2", None, "c", "第38条の2　…", "", [], [], [])
    edits = {"規約|第38条の2": {"text": "第38条の2　…", "note": "最初の経緯／11月06日 08:57：二つ目"}}
    assert edit_note(edits, a) == "最初の経緯\n11月06日 08:57：二つ目"
