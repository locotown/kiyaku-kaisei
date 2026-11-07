"""検証（壊れ方の観点）で見つかった不具合の再発を防ぐテスト。API は呼ばない。"""

from tests.test_partial import board_work  # noqa: F401  (pytest の fixture)


def test_page_css_cannot_close_style():
    """資料名を CSS に入れるとき、</style> で抜けてスクリプトが動かない。"""
    from core.printstyle import page_css
    css = page_css('</style><img src=x onerror=alert(1)>試験"組合', ident='a<b')
    assert "<" not in css and ">" not in css and "</style" not in css and "”" in css


def test_org_name_in_print_pages_is_safe(board_work):
    M, store, c, wid, _, _ = board_work
    c.post(f"/works/{wid}/org", data={"org": "</style><img src=x onerror=alert(1)>試験\n管理組合"})
    assert store.load(wid)["org"] == "</style><img src=x onerror=alert(1)>試験 管理組合"    # 改行は空白に
    for path in ("taiou", "kozo", "minaoshi/shukudai"):
        html = c.get(f"/works/{wid}/{path}").text
        assert "<img src=x" not in html, path


def test_bad_ids_and_values_do_not_500(board_work):
    M, store, c, wid, _, _ = board_work
    assert c.get("/works/" + "a" * 300).status_code == 404
    assert c.post(f"/works/{wid}/final-blanks", data={"f|bad": "1", "f|a|b|xx": "1", "f|a|b|99999999": "1"}).status_code in (200, 303)
    assert c.post(f"/works/{wid}/version", data={"version": "でたらめ"}).status_code == 400


def test_meeting_date_is_checked(board_work):
    """形の違う総会の日は保存しない。前に保存された壊れた値でも、作業の画面は開ける。"""
    M, store, c, wid, _, _ = board_work
    r = c.post(f"/works/{wid}/meeting", data={"m_result_0": "可決", "m_date": "2026/11/08"})
    assert r.status_code == 400
    w = store.load(wid)
    w["meeting"] = {"name": "", "date": "2026/11/08", "effective": "令和9年4月1日", "results": {"規約": "可決"}, "edits": {}}
    store.save(wid, w)
    assert c.get(f"/works/{wid}").status_code == 200


def test_board_autosave_keeps_other_tabs_items(board_work):
    """自動保存は変えた議題だけを使う（2つのタブで、古いタブが別のタブの判断を元に戻した）。"""
    import json
    M, store, c, wid, _, _ = board_work
    paper = M._board(store.load(wid))
    if len(paper.items) < 2:
        return
    from core.board import DECISIONS
    d0 = DECISIONS[paper.items[0].tier][0]
    d1 = [x for x in DECISIONS[paper.items[1].tier] if x][-1]
    c.post(f"/works/{wid}/board/decisions", data={"b_decision_1": d1, "b_touched": json.dumps(["b_decision_1"])})
    # 古いタブ：議題1は空のまま、議題0のメモだけを変えて送る
    c.post(f"/works/{wid}/board/decisions", data={"b_decision_0": d0, "b_note_0": "古いタブのメモ", "b_decision_1": "",
                                                  "b_touched": json.dumps(["b_note_0"])})
    dec = store.load(wid)["board_decisions"]
    assert dec["1"]["decision"] == d1 and dec["0"]["note"] == "古いタブのメモ"
