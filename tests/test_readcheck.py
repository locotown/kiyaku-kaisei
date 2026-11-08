"""読み込んだ規約が今有効な版かの確かめ（課題①②）のテスト。API は呼ばない。"""

from pathlib import Path

from core.collection import segment
from core.corpus import Corpus
from core.readcheck import history, memo_lines
from core.split import split_kiyaku
from tests.test_partial import board_work  # noqa: F401  (pytest の fixture)

ROOT = Path(__file__).resolve().parents[1]
BASE = "".join(f"（見出し{i}）\n第{i}条　規定{i}とする。\n" for i in range(1, 7))


def test_memo_lines_inside_articles():
    """条の文の中のメモらしい文を拾う。規約の文（議事録の条など）は拾わない。"""
    k = split_kiyaku((BASE + "（議事録）\n第7条　総会の議事については、議長は議事録を作成しなければならない。\n"
                      "（専有部分）\n第8条　専有部分とする。どちらが決議されたかは要確認（2026-10-07）\n").splitlines())
    got = memo_lines(Corpus(k))
    assert [m["article"] for m in got] == ["第8条"] and "どちらが" in got[0]["text"]
    assert not memo_lines(Corpus(split_kiyaku(BASE.splitlines())))


def test_history_lists_articles_from_records():
    """規約集の改正の記録（改正履歴の文書・本文から外した「◆ …で改正」の注記）に出てくる条を並べる。"""
    text = ("○○マンション管理規約\n" + BASE.replace("第3条　規定3とする。", "第3条　規定3とする。\n◆ 第35期定期総会で改正") +
            "改正履歴\n第20期定期総会　第12条・第18条を改正\n第22期定期総会　ペット飼育細則を制定\n")
    c = segment(text.splitlines())
    h = history(c)
    assert h["count"] >= 3 and "第12条" in h["articles"] and "第18条" in h["articles"]
    assert any("第35期" in e["text"] for e in h["entries"])


def test_version_answer_saved_and_shown(board_work):
    """ステップ1：版の答えを保存でき、「いいえ」「分からない」なら重ね合わせ方を案内する。"""
    M, store, c, wid, _, _ = board_work
    page = c.get(f"/works/{wid}").text
    assert 'id="readcheck"' in page and "これまでの改正を全部反映した版かを確かめてください" in page
    c.post(f"/works/{wid}/version", data={"version": "分からない"})
    page = c.get(f"/works/{wid}").text
    assert store.load(wid)["version"] == "分からない" and "読み込むときに「分からない」と答えました" in page
    assert "改正後の文に差し替える" in page
    c.post(f"/works/{wid}/version", data={"version": "はい"})
    assert "改正を全部反映した版」として読み込みました" in c.get(f"/works/{wid}").text
    assert c.post(f"/works/{wid}/version", data={"version": "でたらめ"}).status_code == 400
    assert store.load(wid)["version"] == "はい"                     # 不正な値で、保存済みの答えを消さない
    c.post(f"/works/{wid}/version", data={"version": ""})
    assert store.load(wid)["version"] == ""
