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
