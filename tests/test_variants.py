"""今の規約にもともとある両案（標準管理規約の（ア）（イ））を理事会で選び、最新の規約に選んだ案だけを残す（計画A）。AI は使わない。"""

from datetime import date

from core.consolidate import consolidate
from core.corpus import Corpus
from core.split import split_kiyaku
from core.variants import groups, picks
from tests.test_partial import board_work  # noqa: F401  (pytest の fixture)

TEXT = """（目的）
第1条　目的とする。
〔※住宅宿泊事業に使用することを可能とする場合、禁止する場合に応じて、次のように規定〕
　（ア）住宅宿泊事業を可能とする場合　
（専有部分の用途）
第2条　住宅宿泊事業に使用することができる。
　（イ）住宅宿泊事業を禁止する場合　
（専有部分の用途）
第2条　住宅宿泊事業に使用してはならない。
（範囲）
第3条　範囲とする。
〔※管理組合における電磁的方法の利用状況に応じて、次のように規定〕
　（ア）電磁的方法が利用可能ではない場合　
（届出）
第4条　書面により届け出る。
　（イ）電磁的方法が利用可能な場合　
（届出）
第4条　書面又は電磁的方法により届け出る。
〔※管理組合における電磁的方法の利用状況に応じて、次のように規定〕
　（ア）電磁的方法が利用可能ではない場合　
（通知）
第5条　書面で通知する。
　（イ）電磁的方法が利用可能な場合　
（通知）
第5条　書面又は電磁的方法で通知する。
（組合）
第6条　組合を置く。
"""


def kiyaku():
    return split_kiyaku(TEXT.splitlines())


def test_groups_by_note_and_options():
    gs = groups(Corpus(kiyaku()))
    assert [g["topic"] for g in gs] == ["住宅宿泊事業に使用することを可能とする場合、禁止する場合", "管理組合における電磁的方法の利用状況"]
    elec = gs[1]
    assert elec["articles"] == ["4", "5"]                                   # 同じ注記の条は1問にまとめる
    assert elec["options"] == [{"mark": "ア", "label": "電磁的方法が利用可能ではない場合"},
                               {"mark": "イ", "label": "電磁的方法が利用可能な場合"}]


def test_amended_articles_are_left_out_of_the_question():
    gs = groups(Corpus(kiyaku()), {("規約", "4")})
    elec = gs[1]
    assert elec["articles"] == ["5"] and elec["amended"] == ["4"]
    assert len(groups(Corpus(kiyaku()), {("規約", "2")})) == 1                 # 全部の条を書き直す問は出さない


def test_consolidate_keeps_only_the_chosen_option():
    k = kiyaku()
    gs = groups(Corpus(k))
    pk = picks(gs, {gs[0]["key"]: "イ", gs[1]["key"]: "ア"})["規約"]
    assert pk == {"2": "イ", "4": "ア", "5": "ア"}
    text = "\n".join(ln for b in consolidate(k, [], "規約", date(2027, 1, 24), "総会", pk) for ln in b.lines)
    assert "使用してはならない" in text and "使用することができる" not in text
    assert "書面により届け出る" in text and "書面又は電磁的方法により" not in text
    assert "〔ア案〕" not in text and "〔イ案〕" not in text
    both = "\n".join(ln for b in consolidate(k, [], "規約") for ln in b.lines)   # 選ばなければ両方残す（今までどおり）
    assert "使用してはならない" in both and "使用することができる" in both and "〔ア案〕" in both


def test_invalid_choice_is_ignored():
    gs = groups(Corpus(kiyaku()))
    assert picks(gs, {gs[0]["key"]: "ウ", "nokey": "ア"}) == {}


def test_save_and_show_on_step4(board_work):
    """標準管理規約のサンプルで、ステップ4に「今の規約の両案」が出て、選ぶと保存され、ステップ1の知らせから外れる。"""
    M, store, c, wid, _, _ = board_work
    v = M.variant_view(wid, store.load(wid))
    keys = {g["topic"]: g["key"] for g in v["groups"]}
    assert "管理組合における電磁的方法の利用状況" in keys and v["open"] == len(v["groups"])
    page = c.get(f"/works/{wid}").text
    assert 'id="variants"' in page and "今の規約の両案" in page
    k = keys["管理組合における電磁的方法の利用状況"]
    j = c.post(f"/works/{wid}/variants", data={f"v_{k}": "ア", "v_bogus": "ア"}, headers={"Accept": "application/json"}).json()
    assert j["ok"] and j["choices"] == {k: "ア"}
    w = store.load(wid)
    assert w["variant_choices"] == {k: "ア"} and w["variant_history"]
    v = M.variant_view(wid, w)
    assert "第17条" in v["chosen"] and v["open"] == len(v["groups"]) - 1
    s1 = c.get(f"/works/{wid}").text
    s1 = s1[s1.index('id="documents"'):s1.index('id="findings"')]
    assert "第17条、" not in s1.split("両案（（ア）（イ）など）が残っている条があります：")[1].split("。")[0]
    c.post(f"/works/{wid}/variants", data={f"v_{k}": ""}, headers={"Accept": "application/json"})   # まだ選ばないに戻す
    assert store.load(wid)["variant_choices"] == {}
