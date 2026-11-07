"""規約集の構成表（計画F1）のテスト。API は呼ばない。"""

from pathlib import Path

from core.corpus import Corpus
from core.ingest import load_collection
from core.kozo import build, delegations, to_html
from tests.test_partial import board_work  # noqa: F401  (pytest の fixture)

ROOT = Path(__file__).resolve().parents[1]


def _collection():
    return Corpus.from_collection(load_collection(ROOT / "evals/data/old_collection.txt"))


def test_delegations_pick_only_items_left_to_other_rules():
    """「別に定める」「細則で定める」を拾い、「この規約に別に定めるもののほか」（規約の中を指す）は拾わない。"""
    rows = delegations(_collection())
    got = {(r["article"], r["matter"]) for r in rows}
    assert ("第15条", "駐車場の使用・使用料") in got and ("第37条", "外部の役員の選任方法") in got
    assert ("第62条", "管理費等の徴収日・臨時の徴収") in got
    assert not any(r["article"] == "第56条" for r in rows)   # 「この規約に別に定めるもののほか」


def test_build_matches_rules_and_finds_wrong_citation():
    """細則が引いている条で対応を決め、見出しから見て番号がずれた引用を見つける（駐車場使用細則は第16条と引くが、駐車場は第15条）。"""
    k = build(_collection())
    by = {r["article"]: r for r in k["rows"]}
    assert by["第19条"]["status"] == "ある" and "ペット飼育細則" in by["第19条"]["rules"][0]
    assert by["第15条"]["status"] == "ある" and "番号のずれ" in by["第15条"]["wrong"][0]
    assert by["第37条"]["status"] == "見当たらない" and by["第39条"]["status"] == "見当たらない"
    bad = k["bad_cites"]
    assert len(bad) == 1 and "第16条" in bad[0]["cited"] and "「駐車場の使用」は第15条です" in bad[0]["note"]
    page = to_html(k, "規約集の構成表")
    assert "ずれている" in page and "見当たらない" in page and "AI は使っていません" in page and "法的助言ではありません" in page


def test_kozo_page_from_work(board_work):
    """作業の画面（ステップ1）から開ける。細則を読み込んでいない作業では、そう書く。"""
    M, store, c, wid, _, _ = board_work
    assert f'href="/works/{wid}/kozo"' in c.get(f"/works/{wid}").text
    page = c.get(f"/works/{wid}/kozo").text
    assert "規約がほかの決まりに任せている事項" in page and "細則は読み込んでいません" in page and "./#documents" in page
