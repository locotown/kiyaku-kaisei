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
    assert len(paper.items) >= 2, "議題が2つ以上ある作業で確かめる"
    from core.board import DECISIONS
    d0 = DECISIONS[paper.items[0].tier][0]
    d1 = [x for x in DECISIONS[paper.items[1].tier] if x][-1]
    c.post(f"/works/{wid}/board/decisions", data={"b_decision_1": d1, "b_touched": json.dumps(["b_decision_1"])})
    # 古いタブ：議題1は空のまま、議題0のメモだけを変えて送る
    c.post(f"/works/{wid}/board/decisions", data={"b_decision_0": d0, "b_note_0": "古いタブのメモ", "b_decision_1": "",
                                                  "b_touched": json.dumps(["b_note_0"])})
    dec = store.load(wid)["board_decisions"]
    assert dec["1"]["decision"] == d1 and dec["0"]["note"] == "古いタブのメモ"


def test_note_of_in_article_variant_does_not_move_to_next_article():
    """条の中の両案（項だけが（ア）（イ）に分かれる）の注記を、次の条の注記にしない。
    （改正前の標準管理規約で、第19条の2の中の注記を第20条のものにして、AI が「第20条の前の注記を削る」と書いた）"""
    from core.ingest import load_kiyaku
    k = load_kiyaku("evals/data/r7_tantou_before.txt")
    a20 = next(a for a in k.articles if a.number == "20")
    assert a20.note == ""
    assert next(a for a in k.articles if a.number == "17" and a.variant == "ア").note   # 条ごとの両案の注記は残る


def test_taisho_old_column_shows_current_caption():
    """新旧対照表の現行の列は、今の規約の見出しを出す。見出しが変わる条は印を付け、見出しを本文の最後に重ねない。"""
    from core.draft import Amendment, Draft
    from core.model import Article, Kiyaku, Paragraph
    from core.taisho import _html_table, rows
    k = Kiyaku(articles=[Article(number="24", caption="必要箇所への立入り",
                                 paragraphs=[Paragraph(1, "理事長は立ち入ることができる。"), Paragraph(2, "拒んではならない。")])])
    a = Amendment(kind="改正", article="第24条", before_article="第24条", caption="必要箇所への立入り等",
                  text="第24条　理事長は立ち入り、又は保存行為をすることができる。\n2　拒んではならない。", reason="r",
                  finding_refs=[], law_basis=[], standard_basis=[])
    rs = rows(Draft(amendments=[a], notes=""), k)
    assert rs[0]["old_caption"] == "必要箇所への立入り"
    html = _html_table([(1, rs[0])], "")
    old_cell = html.split('class="c-old">')[1]
    assert "<mark>等</mark>" in html and "必要箇所への立入り" in old_cell and "立入り等" not in old_cell.split("</td>")[0]
    new_cell = html.split('class="c-new">')[1].split("</td>")[0]
    assert not new_cell.rstrip().endswith("）")                                     # 本文の最後に見出しを重ねない


def test_related_labels_main_rules_and_adds_amended_text():
    """細則が引く規約の条は「今の規約」として渡し、同じ総会で直す条なら改定案の文も並べる。"""
    from app.main import _related
    from core.corpus import Corpus
    from core.draft import Amendment, Draft
    from core.model import Article, Kiyaku, Paragraph
    main = Kiyaku(articles=[Article(number="45", caption="招集手続", paragraphs=[Paragraph(1, "旧の文。")])])
    corpus = Corpus.of(main)
    am = Amendment(kind="改正", article="第45条", before_article="第45条", caption="招集手続", text="第45条　新しい文。",
                   reason="", finding_refs=[], law_basis=[], standard_basis=[])
    out = _related(corpus, "規約", "第3条", "規約第45条第8項の定めるところによる", draft=Draft(amendments=[am], notes=""))
    assert out[0]["source"] == "今の規約" and "旧の文" in out[0]["text"]
    assert any("改定案" in o["source"] and "新しい文" in o["text"] for o in out)
