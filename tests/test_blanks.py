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
    assert [(x["where"], x["n"]) for x in in_draft(draft)] == [("第52条", 1), ("総会運営細則 第3条", 4)]   # 行の番号は規約が先
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
    assert "「○」の空欄が残っている条があります（1か条）" in page and "○か月に1回" in page and "/articles#row1" in page


def test_step6_tells_blanks_in_latest_rules(board_work, monkeypatch):
    """最新の規約に「○」が残っていれば、ステップ6で一覧を出し、今回の改定で入った条とそれ以外で、入れる数字の出どころを分けて案内する。"""
    M, store, c, wid, _, _ = board_work
    finals = [{"n": 0, "doc": "規約", "title": "t", "blocks": [], "left": [], "count": 1, "history": "h", "variants": [],
               "blanks": [{"where": "第35条（役員）", "snippets": ["二 副理事長 ○名"], "changed": True},
                          {"where": "第56条（会計年度）", "snippets": ["…毎年○月○日から…"], "changed": False}]}]
    finals[0]["blank_slots"] = [dict(x, slots=[{"i": 0, "before": "二 副理事長 ", "after": "名", "mark": "○"}], values=[])
                                for x in finals[0]["blanks"]]
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



def test_slots_fill_and_suggest():
    """入力欄の位置・数字の入れ方・今の規約の数字（計画D3）。"""
    from core.blanks import fill, slots, suggest

    t = "2　理事が○分の1以上の理事の同意を得て理事会の招集を請求した場合には、理事長は速やかに招集しなければならない。\n二　副理事長　○名"
    ss = slots(t)
    assert [(x["before"], x["after"]) for x in ss] == [("2 理事が", "分の1以上…"), ("二 副理事長 ", "名")]
    assert "理事が4分の1以上" in fill(t, ["4", ""]) and "副理事長　○名" in fill(t, ["4", ""])   # 空の値は「○」のまま
    assert suggest(t, "2　理事が4分の1以上の理事の同意\n二　副理事長　2名") == ["4", "2"]
    assert suggest(t, "2　理事が○分の1以上") == ["", ""]                                  # 今の規約も空欄なら初めの値はなし


def test_step4_blank_inputs_fill_the_draft(board_work):
    """ステップ4の「空欄に入れる数字」：入れた数字を改定案の条に入れ、委員会で直した文として記録する。空にすると「○」に戻る。"""
    M, store, c, wid, _, _ = board_work
    w = store.load(wid)
    am = w["draft"]["amendments"][0]
    am["text"] += "\n9　理事長は、○か月に1回以上、職務の執行の状況を理事会に報告しなければならない。"
    store.update(wid, draft=w["draft"])
    key = f"{am.get('document') or '規約'}|{am['article']}"
    page = c.get(f"/works/{wid}").text
    assert 'id="blanks"' in page and f'name="k_{key}_0"' in page and "空欄に入れる数字" in page
    r = c.post(f"/works/{wid}/blanks", data={f"k_{key}_0": "3"}, headers={"accept": "application/json"})
    assert r.status_code == 200 and r.json()["changed"] == [am["article"]]
    w = store.load(wid)
    text = w["draft"]["amendments"][0]["text"]
    assert "3か月に1回以上" in text and "○" not in text
    assert "空欄（○）に数字を入れた" in w["human_edits"][key]["note"] and w["blank_fills"][key]["values"] == ["3"]
    page = c.get(f"/works/{wid}").text
    assert "「○」の空欄が残っている条があります" not in page and 'value="3"' in page   # 入れた数字は欄に残り、直せる
    c.post(f"/works/{wid}/blanks", data={f"k_{key}_0": ""}, headers={"accept": "application/json"})
    assert "○か月に1回以上" in store.load(wid)["draft"]["amendments"][0]["text"]


def test_step6_final_fills_are_saved_and_applied(board_work):
    """ステップ6：最新の規約に残る空欄に入れた数字を保存し、最新の規約のブロックに入れる（計画D3）。"""
    from core.blanks import fill_blocks

    M, store, c, wid, _, _ = board_work
    c.post(f"/works/{wid}/final-blanks", data={"f|規約|第56条（会計年度）|0": "4", "f|規約|第56条（会計年度）|1": "1"},
           headers={"accept": "application/json"})
    ff = store.load(wid)["final_fills"]
    assert ff == {"規約": {"第56条（会計年度）": ["4", "1"]}}
    blocks = [Block("article", ["（会計年度）", "第56条　会計年度は、毎年○月○日から翌年○月○日までとする。"])]
    fill_blocks(blocks, ff["規約"])
    assert blocks[0].lines[1] == "第56条　会計年度は、毎年4月1日から翌年○月○日までとする。"


def test_lines_show_whole_sentence_with_inputs():
    """入力欄は、前後の数文字ではなく項の文の中に置く（確認ボード 第22回：前後の文がないと数字を入れられない）。"""
    from core.blanks import lines

    t = "第54条　理事会は、理事長が招集する。\n3　前項の規定による請求があった日から○日以内に、その請求があった日から○日以内の日を理事会の日とする。"
    got = lines(t)
    assert len(got) == 1 and [p.get("slot") for p in got[0] if "slot" in p] == [0, 1]
    assert "".join(p.get("t", "□") for p in got[0]) == "3　前項の規定による請求があった日から□日以内に、その請求があった日から□日以内の日を理事会の日とする。"


def test_mansion_name_suggestion_drops_suffix():
    import app.main as M

    raw = [{"where": "第1条（目的）", "slots": [{"i": 0, "before": "…この規約は、", "after": "マンション…", "mark": "○○"}], "lines": [], "changed": False}]
    got = M.blank_slots(raw, {}, "グリーンヒルマンション管理組合")
    assert got[0]["slots"][0]["suggest"] == "グリーンヒル"


def test_latest_rules_leave_out_tables_and_working_notes():
    """最新の規約：別表・様式は「原本のとおり」と書いて中身を入れない。前置きの作業用の説明の文も入れない（11/7 作者の判断）。"""
    from datetime import date

    from core.consolidate import consolidate, left_out
    from core.split import split_kiyaku

    text = ("○○マンション管理規約\n議事録で内容は確認済。第31期の改正は規約4条の改正をまとめて1つの注記で示す形式で、別紙にも載っている\n"
            "（目的）\n第1条　目的とする。\n（定義）\n第2条　定義する。\n（範囲）\n第3条　範囲とする。\n（効力）\n第4条　効力を持つ。\n"
            "附　則\nこの規約は、令和元年4月1日から効力を発する。\n別表第1　対象物件の表示\n物件名　○○マンション\n別表第2　共用部分\n"
            "管理費の表\n地下駐車場　8,000円　17台\n様式1　届出書\n")
    k = split_kiyaku(text.splitlines())
    lo = left_out(k)
    assert lo["tables"] == ["別表第1", "別表第2", "様式1"] and len(lo["notes"]) == 1
    blocks = consolidate(k, [], "規約", date(2027, 5, 23), "総会")
    alltext = "\n".join(x for b in blocks for x in b.lines)
    assert "議事録で内容は確認済" not in alltext and "○○マンション管理規約" in alltext   # 題名は残す
    assert "地下駐車場" not in alltext and "別表第1・別表第2・様式1は、今回の改正はありません。原本のとおりです" in alltext
