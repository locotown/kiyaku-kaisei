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


def test_step2_groups_add_change_and_must(board_work):
    """ステップ2（C案）：今の規約に定めがない指摘は「足す」の表、定めがある推奨は「変える」のカード、必須は下に閉じて置く。"""
    M, store, c, wid, _, _ = board_work
    w = store.load(wid)
    base = w["findings"][0]
    w["findings"] = [dict(base, category="必須"), dict(base, category="推奨", current_excerpt="", topic_id="5"),
                     dict(base, category="推奨", current_excerpt="今の文", topic_id="1-3"), dict(base, category="参考", current_excerpt="今の文", topic_id="10")]
    w["decisions"] = {"0": {"decision": "採用", "reason": ""}}
    store.save(wid, w)
    page = c.get(f"/works/{wid}").text
    assert 'id="sec-add"' in page and 'id="sec-chg"' in page and 'id="sec-ref"' in page and 'id="sec-must"' in page
    assert 'class="fitem arow" id="f-1"' in page and 'class="cmp1"' in page and 'data-only="1"' in page
    s2 = page.split('<section class="panel" data-step="decide"')[1].split('<section class="panel"')[0]
    assert 'class="tiles"' not in s2 and 'data-filter' not in s2


def test_bulk_add_scope_only_touches_findings_without_current_rule(board_work):
    M, store, c, wid, _, _ = board_work
    w = store.load(wid)
    base = w["findings"][0]
    w["findings"] = [dict(base, category="推奨", current_excerpt=""), dict(base, category="推奨", current_excerpt="今の文"),
                     dict(base, category="必須", current_excerpt="")]
    w["decisions"] = {}
    store.save(wid, w)
    j = c.post(f"/works/{wid}/decisions/bulk", data={"scope": "足す", "decision": "採用", "only_open": "1"}).json()
    d = store.load(wid)["decisions"]
    assert j["changed"] == 1 and d["0"]["decision"] == "採用" and "1" not in d and "2" not in d


def test_board_decision_is_buttons_like_step2(board_work):
    """ステップ4の判断は、ステップ2と同じボタン（ラジオ）の形。段ごとの案と「未判断」が並び、保存した判断に印が付く（計画B）。"""
    import re

    M, store, c, wid, _, _ = board_work
    c.post(f"/works/{wid}/board/decisions", data=FORM)
    page = c.get(f"/works/{wid}").text
    assert '<select name="b_decision_' not in page
    for key, val in FORM.items():
        if not key.startswith("b_decision_"):
            continue
        group = re.search(rf'<div class="mini2 bseg n\d"[^>]*>(.*?)</div>', page[page.index(f'name="{key}"') - 400:], re.S).group(1)
        assert f'value="{val}" checked' in group and ">未判断</label>" in group
    # 判断していない議題は「未判断」に印が付く
    c.post(f"/works/{wid}/board/decisions", data={})
    page = c.get(f"/works/{wid}").text
    assert re.search(r'name="b_decision_0" value="" checked>未判断', page)


def test_taisho_rewritten_when_opened(board_work):
    """前に作った新旧対照表も、開いたときに今の作り（スマホの項ごとの見比べ）で書き直す。AI は使わない（計画C）。"""
    M, store, c, wid, _, _ = board_work
    p = store.path(wid) / "taisho.html"
    p.write_text("<html>前の作りの表</html>", encoding="utf-8")
    page = c.get(f"/works/{wid}/taisho").text
    assert "前の作りの表" not in page and ".pairs { display: none; }" in page


def test_document_back_link_returns_to_its_step(board_work):
    """資料の「作業の画面に戻る」：作業の画面から開いたときは開いたときの画面へ（history.back）、
    直接開いたときは資料を作ったステップへ。新旧対照表から戻るとステップ4になり混乱した（確認ボード 第20回の気づき）。"""
    M, store, c, wid, _, _ = board_work
    page = c.get(f"/works/{wid}/taisho").text
    assert 'href="./#next" class="back"' in page and "history.back()" in page
    work = c.get(f"/works/{wid}").text
    assert "開く（印刷用）" not in work and "（見る・印刷する）" in work   # 印刷のときだけ使うように見えた（同じ回の気づき）
