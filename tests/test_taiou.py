"""今の規約と標準管理規約の条の対応表（計画E1）のテスト。API は呼ばない。"""

from pathlib import Path

from core.corpus import Corpus
from core.ingest import load_collection
from core.sources import standard
from core.taiou import match, to_html
from tests.test_partial import board_work  # noqa: F401  (pytest の fixture)

ROOT = Path(__file__).resolve().parents[1]


def test_match_renumbered_old_rules():
    """条番号がずれた古い規約でも、見出しと文で標準管理規約の条に対応づける。独自の条と、標準にあって無い条を分ける。"""
    co = Corpus.from_collection(load_collection(ROOT / "evals/data/old_collection.txt"))
    t = match(co.main, standard())
    by = {r["label"]: r for r in t["rows"]}
    assert by["第37条"]["std_label"] == "第35条" and by["第37条"]["kind"] == "違う"        # 役員（番号がずれている）
    assert by["第31条"]["kind"] == "今の規約だけ" and by["第19条"]["kind"] == "今の規約だけ"  # 町内会費・ペット（架空の独自の条）
    assert by["第12条"]["amount"] != "大"                                                   # 標準の両案のうち近い案と比べる
    missing = {m["label"] for m in t["missing"]}
    assert {"第31条の3", "第32条の2", "第67条の4"} <= missing                                # 国内管理人・防火管理者・管理命令
    assert sum(t["counts"].values()) == len(t["rows"]) + len(t["missing"])
    page = to_html(t, "対応表", touched={"37"})
    assert "今回の改定案で直す" in page and "今の規約だけ" in page and "AI は使っていません" in page


def test_taiou_page_from_work(board_work):
    M, store, c, wid, _, _ = board_work
    assert f'href="/works/{wid}/taiou"' in c.get(f"/works/{wid}/minaoshi").text     # 対応表は②に置く
    page = c.get(f"/works/{wid}/taiou").text
    assert "標準管理規約の条の対応表" in page and "標準管理規約にあって、今の規約にない条" in page and "./#documents" in page
