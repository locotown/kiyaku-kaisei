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


def test_various_wordings_and_caption_variants():
    """実在の規約集の書き方の幅（11/7 作者の規約集で確かめて直した）：
    「別途細則を定める」「細則を定めるものとする」も拾う。細則の前文に書かれた根拠の条も見る。
    見出しを略して引く・送り仮名が違うだけのものは、ずれにしない。"""
    from core.kozo import _same_caption, citations
    from core.model import Kiyaku
    from core.split import split_kiyaku

    main = split_kiyaku(("（使用細則）\n第17条　対象物件の使用については、必要に応じて使用細則等別途細則を定めるものとする。\n"
                         "（管理）\n第20条　管理組合が管理する。\n2　管理組合は、前項の工事について、細則を定めるものとする。\n"
                         "（必要箇所への立入り）\n第22条　必要箇所への立入りを請求できる。\n（効力）\n第23条　効力を持つ。\n（組合）\n第24条　組合を置く。\n").splitlines())
    rule = split_kiyaku(("管理規約第17条の規定に基づいて、次のとおり定める。\n第1条　この細則は、規約第22条（必要箇所の立ち入り）による。\n"
                         "第2条　守る。\n第3条　改廃する。\n").splitlines())
    co = Corpus(main, {"使用細則": rule})
    got = {r["article"]: r for r in delegations(co)}
    assert "第17条" in got and "第20条" in got and got["第20条"]["para"] == "第2項"
    cites = {c["number"]: c for c in citations(co)}
    assert "17" in cites and cites["22"]["ok"] and "見出しの書き方が少し違います" in cites["22"]["note"]
    assert _same_caption("窓ガラス等の改良", "敷地及び共用部分等の管理に関する責任と負担並びに窓ガラス等の改良")
    assert not _same_caption("駐車場の使用", "敷地及び共用部分等の第三者の使用")
    assert isinstance(main, Kiyaku)


def test_other_rules_are_their_own_documents():
    """「○○ルール」「申し合わせ」などは「その他の決まり」として分ける（規約・細則に混ぜない。改正対応の対象外）。
    個々のルールの見出し（①…ルール）は同じ文書の中に入れる。本文の「議案の要領」などは拾わない。"""
    from core.collection import segment

    body = "".join(f"（見出し{i}）\n第{i}条　規定{i}とする。\n" for i in range(1, 7))
    text = ("○○マンション管理規約\n" + body + "第7条　招集通知には、議案の要領を示さなければならない。\n"
            "○○マンション　ルールの新設・改定\n① 日除け天幕設置に関するルール\n設置業者は一社に限る。\n"
            "② 自転車置場使用料徴収方法変更に関するルール\n毎月10日に引き落とす。\n"
            "○○マンション駐車場使用細則\n第1条　目的とする。\n第2条　資格とする。\n第3条　使用料とする。\n")
    c = segment(text.splitlines())
    kinds = [(d.kind, d.title) for d in c.documents]
    assert ("その他の決まり", "○○マンション　ルールの新設・改定") in kinds
    other = next(d for d in c.documents if d.kind == "その他の決まり")
    assert "1 日除け天幕設置に関するルール" in other.lines and len([k for k, _ in kinds if k == "その他の決まり"]) == 1
    main = c.main.kiyaku
    assert len(main.articles) == 7 and not any("日除け" in x for x in main.appendix)   # 規約に混ぜない
    assert Corpus.from_collection(c).rules.keys() == {"○○マンション駐車場使用細則"}     # 点検の対象は細則だけ
