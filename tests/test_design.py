"""画面の共通部品（帯をやめた「次にすること」の枠など）と、想定ユーザーでの確認から直したところのテスト。API は呼ばない。"""

from tests.test_partial import FORM, board_work  # noqa: F401  (pytest の fixture)


def test_revert_board_change_does_not_mark_explain_or_meeting_stale(board_work):
    """説明・総会の結果を作ったときの判断に戻しただけなら、「作り直し」「保存し直し」を求めない（戻しただけで費用をかけない）。"""
    M, store, c, wid, _, _ = board_work
    snap = M._board_snapshot(store.load(wid)["board_decisions"])
    store.update(wid, explain={"title": "t", "items": []}, explain_board=snap, explain_stale=False,
                 meeting={"results": {"規約": "可決"}}, meeting_board=snap, board_changed_after_meeting="")
    other = dict(FORM)
    key = next(k for k in FORM if k.startswith("b_decision_"))
    other[key] = "見送り" if FORM[key] != "見送り" else "採用"
    c.post(f"/works/{wid}/board/decisions", data=other)
    w = store.load(wid)
    assert w["explain_stale"] and w["board_changed_after_meeting"]
    c.post(f"/works/{wid}/board/decisions", data=FORM)          # 元に戻す
    w = store.load(wid)
    assert not w["explain_stale"] and not w["board_changed_after_meeting"]


def test_other_causes_keep_stale_mark(board_work):
    """条の文を直したなど、判断以外で古くなった印は、判断を戻しても外さない。"""
    M, store, c, wid, _, _ = board_work
    snap = M._board_snapshot(store.load(wid)["board_decisions"])
    store.update(wid, explain={"title": "t", "items": []}, explain_board=snap, explain_stale=True, explain_stale_reason="other")
    c.post(f"/works/{wid}/board/decisions", data=FORM)
    assert store.load(wid)["explain_stale"]


def test_steps_have_next_panel_and_no_bottom_bar(board_work):
    M, store, c, wid, _, _ = board_work
    page = c.get(f"/works/{wid}").text
    assert 'class="bar"' not in page and 'class="nx nxb nxs"' in page and 'class="actend nxs"' in page
    assert "次にすること" in page and "/static/parts.css" in page


def test_board_reason_says_choice_not_undecided(board_work):
    """〔選択〕を選んでいないだけのときに「判断していない議題」と言わない（想定ユーザーでの確認で分かった）。"""
    M, store, c, wid, _, _ = board_work
    w = store.load(wid)
    w["board_decisions"] = {k: {**v, "picked": {}} for k, v in w["board_decisions"].items()}
    st = M.board_state(w)
    if st.get("needs_choice") and len(st["undecided"]) == len(st["needs_choice"]):
        assert "まだ判断していない議題" not in st["reason"] and "組合が選ぶ点" in st["reason"]


def test_decision_save_returns_new_cost_note(board_work):
    M, store, c, wid, _, _ = board_work
    j = c.post(f"/works/{wid}/decisions/0", data={"decision": "採用", "reason": ""}).json()
    assert "ai_draft" in j and "改定案" in j["ai_draft"]


def test_articles_title_has_no_script(board_work):
    """条の文を直す画面の題名にスクリプトが入らない（タブにプログラムの文が出て、位置を戻す仕組みも動かなかった）。"""
    M, store, c, wid, _, _ = board_work
    page = c.get(f"/works/{wid}/articles").text
    title = page[page.index("<title>"):page.index("</title>")]
    assert "<script" not in title and "art-scroll-" in page
