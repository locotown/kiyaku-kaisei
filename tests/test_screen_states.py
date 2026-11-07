"""画面の総点検（状態ごと・ステップごと）で見つけた問題を、自動テストにしたもの。API は呼ばない。

点検の決まり：
- 画面下の帯（.bar）を出さない
- 各ステップの上に「次にすること」（.nx）があり、主なボタンがある
- 資料を作る前のステップ4・5は、上の枠と最後の行が同じことを言わない（最後の行は資料があるときだけ）
- 止まった（エラー）ときは、「済んだ」「作りましょう」ではなく「止まりました。もう一度」と言う
- 総会の結果を記録したあとは、ステップ4で「住民への説明へ」と前の段階へ誘わない
- 先へ進んだ作業のステップ1は、「次は指摘を判断」と言い続けず、いまの段階へ案内する
- 文を切り詰めるときは、先にタグを外す（HTML の途中で切れて、スマホで横にはみ出していた）
"""

import re
from pathlib import Path

from tests.test_partial import FORM, board_work  # noqa: F401  (pytest の fixture)

TPL = Path(__file__).resolve().parent.parent / "app" / "templates"


def section(page: str, step: str) -> str:
    """そのステップの画面（<section class="panel" … id=…>）だけを切り出す（上の進み具合の列にも data-step がある）。"""
    i = page.index('" id="%s">' % step, page.index('<section class="panel"'))
    j = page.find('<section class="panel"', i + 1)
    return page[i: j if j > 0 else len(page)]


def nx_text(page: str, step: str) -> str:
    """そのステップの「次にすること」の枠の文（タグを外す）。"""
    sec = section(page, step)
    i = sec.find('class="nx ')
    if i < 0:
        return ""
    j = sec.find('class="btn"', i)
    return re.sub(r"<[^>]+>|\s+", "", sec[i: j if j > 0 else i + 800].split(">", 1)[1])


def test_no_bottom_bar_and_every_step_has_next_panel(board_work):
    M, store, c, wid, _, _ = board_work
    page = c.get(f"/works/{wid}").text
    assert 'class="bar"' not in page
    for st in ("documents", "findings", "next", "board", "explain", "meeting"):
        sec = section(page, st)
        assert 'class="nx' in sec, st
        assert nx_text(page, st), st


def test_before_board_and_explain_show_preview_without_duplicate_end(board_work):
    """作る前のステップ4・5：本文に「できること」を出し、最後の行（上と同じボタン）は出さない（作者の指摘）。"""
    M, store, c, wid, _, _ = board_work
    store.update(wid, board=None, board_decisions={}, status="改定案あり")
    page = c.get(f"/works/{wid}").text
    s4 = section(page, "board")
    assert 'class="card2 preview"' in s4 and "理事会の検討資料でできること" in s4
    assert 'class="actend' not in s4
    s5 = section(page, "explain")
    assert 'class="card2 preview"' in s5 and 'class="actend' not in s5


def test_error_states_say_stopped(board_work):
    M, store, c, wid, _, _ = board_work
    store.update(wid, status="改定案エラー", error="見本", draft=None, board=None)
    page = c.get(f"/works/{wid}").text
    assert "改定案づくりが途中で止まりました" in nx_text(page, "findings")
    assert "改定案をもう一度作る" in section(page, "findings")
    assert "判断がそろいました" not in nx_text(page, "findings")


def test_board_error_and_explain_error(board_work):
    M, store, c, wid, _, _ = board_work
    store.update(wid, status="検討資料エラー", error="見本", board=None, board_decisions={})
    page = c.get(f"/works/{wid}").text
    assert "検討資料づくりが途中で止まりました" in nx_text(page, "board")


def test_after_meeting_step4_points_to_meeting_not_back(board_work, monkeypatch):
    M, store, c, wid, _, _ = board_work
    real = M.board_state
    monkeypatch.setattr(M, "board_state", lambda w: {**real(w), "ready": True, "needs_redraft": False})   # 理事会の判断が済んだ状態にする
    store.update(wid, explain={"title": "t", "items": []}, meeting={"results": {"規約": "可決"}})
    page = c.get(f"/works/{wid}").text
    assert "総会の結果を見る" in section(page, "board") and "住民への説明へ" not in nx_text(page, "board")
    assert 'class="note2"' in section(page, "board")              # 記録済みの知らせは、注意（赤）ではなく知らせの枠
    store.update(wid, board_changed_after_meeting="11月07日 10:00")
    page = c.get(f"/works/{wid}").text
    assert "総会のあとで判断を変えました" in nx_text(page, "board") and '<p class="warn"><b class="w">総会の結果を記録済み' in section(page, "board")


def test_step6_before_explain_guides_to_step5_but_can_still_save(board_work):
    M, store, c, wid, _, _ = board_work
    store.update(wid, explain=None, meeting=None)
    page = c.get(f"/works/{wid}").text
    s6 = section(page, "meeting")
    assert "総会の前に、住民向けの説明を" in nx_text(page, "meeting")
    assert 'href="#explain"' in s6 and 'form="meetingform"' in s6     # 総会が済んでいれば、ここで保存もできる


def test_step1_points_to_current_stage_when_later(board_work):
    M, store, c, wid, _, _ = board_work
    page = c.get(f"/works/{wid}").text
    t = nx_text(page, "documents")
    assert "次は、指摘を判断します" not in t and "今は「" in t


def test_progress_last_age_is_not_raw_seconds():
    src = (TPL / "work" / "_progress.html").read_text(encoding="utf-8")
    assert "{{ progress.last_age }}秒前" not in src


def test_truncate_strips_tags_first():
    """切り詰める前にタグを外す（〔見出し〕の span の途中で切れ、後ろの部品が崩れて横にはみ出した）。"""
    bad = []
    for p in TPL.rglob("*.html"):
        for m in re.finditer(r"\{\{[^}]*\|truncate\(", p.read_text(encoding="utf-8")):
            if "striptags|truncate(" not in m.group(0):
                bad.append(f"{p.name}: {m.group(0)}")
    assert not bad, bad


# ---- 本物の AI で通した想定ユーザー（スマホの新任理事）の報告から ----

def test_partial_redraft_stays_on_board_step(board_work):
    """対象の条だけ作り直す間は、ステップ3ではなくステップ4の続きとして見せる。"""
    M, store, c, wid, _, _ = board_work
    w = store.load(wid)
    w.update(status="改定案作成中", draft_mode="partial")
    assert M.journey(w, M.board_state(w))["current"] == "board"
    w.update(draft_mode="full")
    assert M.journey(w, M.board_state(w))["current"] == "draft"


def test_journey_marks_are_distinguishable_for_screen_readers(board_work):
    M, store, c, wid, _, _ = board_work
    page = c.get(f"/works/{wid}").text
    assert 'aria-label="済"' not in page and 'aria-label="AI が作り終えた"' in page
    assert "いま開いている画面" in page


def test_done_notice_is_removed_from_address():
    src = (TPL / "work.html").read_text(encoding="utf-8")
    assert "history.replaceState" in src and "done|bulk" in src


def test_explain_prompt_forbids_unstated_facts_and_asks_direction():
    from core.explain import SYSTEM
    assert "渡された資料にない事実" in SYSTEM and "条件付きのまま" in SYSTEM
    assert "厳しくなるのか緩くなるのか" in SYSTEM


# ---- 本物の AI で通した想定ユーザー（スマホの理事長・Mac の委員）の報告から ----

def test_variant_articles_detects_both_options_left():
    """（ア）（イ）や〔ア案〕〔イ案〕の両案が残った条を見つける（最新の規約にそのまま残り、規約として使えなかった）。"""
    from app.main import variant_articles
    from core.consolidate import Block

    blocks = [Block("article", ["〔ア案〕", "（専有部分の用途）", "第12条　住宅として使用する。"]),
              Block("article", ["〔イ案〕", "（専有部分の用途）", "第12条　住宅宿泊事業に使用してはならない。"]),
              Block("article", ["（届出）", "第31条　次のとおり届け出る。", "　（ア）電磁的方法が利用可能ではない場合", "　書面で", "　（イ）電磁的方法が利用可能な場合", "　書面又は電磁的方法で"]),
              Block("article", ["（目的）", "第1条　目的とする。"])]
    assert variant_articles(blocks) == ["第12条", "第31条"]
    # ふつうの列挙の（ア）（イ）は両案ではない（実在の規約・細則でよく使う）
    enum = [Block("article", ["（届出）", "第20条　次の事項を届け出る。", "　（ア）氏名", "　（イ）住所"])]
    assert variant_articles(enum) == []


def test_internal_topic_ids_are_named():
    from core.topics import name_topics

    t = name_topics("第47条の改定のうち論点1-3に当たる部分です。")
    assert "論点1-3" not in t and "「普通決議の定足数」の論点" in t
    t2 = name_topics("（論点10。今回は採用されていません）")          # 1つの数字の論点も（ステップ3の範囲外の点に出ていた）
    assert "論点10" not in t2 and "「区分所有者の責務」の論点" in t2


def test_consult_says_when_owner_count_was_assumed():
    from core.consult import clean_profile as normalize_profile, votes

    p = normalize_profile({"units": "50", "vote_rule": "1戸1議決権"})
    v = votes(p, "普通決議")
    assert "仮に住戸の数と同じ" in str(v["組合員の数"])
    p2 = normalize_profile({"units": "50", "owners": "48", "vote_rule": "1戸1議決権"})
    assert votes(p2, "普通決議")["組合員の数"] == 48


def test_explain_prompt_keeps_subject_and_direction():
    from core.explain import SYSTEM, ExplainItem
    assert "主語と向き" in SYSTEM and "自ら修理" in SYSTEM
    assert "厳しくなるのか緩くなるのか" in ExplainItem.model_fields["impact"].description


# ---- 残る課題を検証して直したもの（11/6 夜） ----

def test_inline_variant_is_detected():
    """別案が本文の同じ行につながったもの（「…とする場合2　…」）も両案として見つける。"""
    from app.main import variant_articles
    from core.consolidate import Block

    b = [Block("article", ["（役員）", "第37条　役員を置く。", "3　理事長は理事会で選ぶ。外部専門家を役員として選任できることとする場合2　理事及び監事は総会で選ぶ。"])]
    assert variant_articles(b) == ["第37条"]


def test_new_supplementary_provision_goes_before_appendix_tables():
    """今回の附則は、今ある附則のすぐあと・別表の前に入る（規約集は「附則 → 別表」の順）。"""
    from datetime import date

    from core.consolidate import consolidate
    from core.split import split_kiyaku

    text = "（目的）\n第1条　目的とする。\n（定義）\n第2条　定義する。\n（範囲）\n第3条　範囲とする。\n（効力）\n第4条　効力を持つ。\n（組合）\n第5条　組合を置く。\n附　則\nこの規約は、令和元年4月1日から効力を発する。\n別表第１　対象物件の表示\n物件名　○○マンション\n"
    k = split_kiyaku(text.splitlines())
    blocks = consolidate(k, [], "規約", date(2027, 1, 24), "総会")
    heads = [b.lines[0] for b in blocks if b.kind == "appendix"]
    new = next(i for i, h in enumerate(heads) if "令和9年1月24日" in h)
    table = next(i for i, h in enumerate(heads) if h.startswith("別表"))
    assert new < table
    # 別表は表の形を再現できないので、中身は入れず「原本のとおり」と書く（11/7 作者の判断（b））
    tb = [b for b in blocks if b.kind == "appendix" and b.lines[0].startswith("別表")][0]
    assert tb.changed == "原本" and "原本のとおり" in tb.lines[1] and "別表第1" in tb.lines[1]
    assert not any("物件名" in x for b in blocks for x in b.lines)


def test_work_name_can_be_changed(board_work):
    M, store, c, wid, _, _ = board_work
    c.post(f"/works/{wid}/org", data={"org": "", "name": "第1回の見直し"})
    assert store.load(wid)["name"] == "第1回の見直し"
    c.post(f"/works/{wid}/org", data={"org": "x", "name": ""})                 # 空なら名前は変えない
    assert store.load(wid)["name"] == "第1回の見直し"


def test_board_item_marks_partially_rewritten_articles(board_work):
    M, store, c, wid, _, _ = board_work
    store.update(wid, draft_mode="partial", draft_partial={"status": "済み", "at": "x", "changed": ["第47条"], "targets": ["第47条"], "check": {}})
    assert "この議題の条（第47条）は、理事会の判断を反映して作り直しました" in section(c.get(f"/works/{wid}").text, "board")


def test_draft_side_notes_are_listed():
    from app.main import draft_side_notes

    w = {"draft": {"notes": "【決議の進め方】\nx\n【あわせて検討するとよい点】（対象外）\n・第48条第十三号：条番号が変わっています。\n・第44条：書き方。\n【使った資料】\ny"}}
    assert draft_side_notes(w) == ["第48条第十三号：条番号が変わっています。", "第44条：書き方。"]


def test_reference_category_is_not_described_as_unrelated_to_the_revision():
    src = (TPL / "work" / "step2_decide.html").read_text(encoding="utf-8")
    assert "法改正とは直接関係しません" not in src


# ---- 知識ベース（正規版）の入口：β版ではなにも変えない ----

def test_kb_entry_is_empty_without_knowledge_base():
    from core import kb
    assert not kb.available() and kb.standard_extra("第36条") == "" and kb.version() == ""


def test_kb_entry_adds_comment_and_choices(tmp_path, monkeypatch):
    import json

    from core import kb
    from core.consult import Handler

    p = tmp_path / "kb.json"
    p.write_text(json.dumps({"meta": {"name": "見本", "sources": [{"file": "x.pdf", "sha": "abc"}]}, "standard": {"36": {
        "comment": {"heading": "第36条関係", "text": "役員の任期については、組合の実情に応じて１～２年で設定する。"},
        "choices": [{"kind": "空欄", "topic": "数を決めて書き入れる", "quote": "役員の任期は○年とする"}],
        "guides": [{"topic": "任期を決める", "options": ["1年", "2年"], "guide": "1〜2年が目安。", "quotes": ["１～２年で設定する"]}]}}},
        ensure_ascii=False), encoding="utf-8")
    monkeypatch.delenv("KIYAKU_KB_OFF")
    monkeypatch.setenv("KIYAKU_KB", str(p))
    kb._load.cache_clear()
    out = Handler(profile={})._get_standard_articles(["第36条"])
    assert "役員の任期は○年とする" in out and "《コメント（第36条関係）》" in out and "《判断の目安：任期を決める》" in out
    assert kb.version() == "見本／x.pdf@abc"
