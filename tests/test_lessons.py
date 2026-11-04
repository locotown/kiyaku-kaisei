"""検証ループ L2：採点役の差し戻し理由から、満たしていない確認項目を取り出す。"""

from evals.lessons import failed_items


def test_failed_items_counts_only_negative_parts():
    ex = """An independent grader found the following criteria are not fully met:
- 改定案のルーブリック（項目1〜11の総合） (partially met): 大部分の項目は満たしていますが、項目4と項目9に問題があるため満点にはできません。
満たしている点：
- 項目1：kaitei.json があり、形も正しいです。
- 項目10：notes は見出しで整理されています。
問題点：
(1) 項目4：第49条で、採用していない論点の変更を混ぜています。指摘の範囲外の変更です。
(2) 項目9：第69条第6項が、削った号を参照したまま残っています。参照先と内容が合いません。
"""
    got = failed_items(ex)
    assert set(got) == {4, 9}
    assert "範囲外" in got[4][0]


def test_satisfied_items_are_not_counted():
    ex = "(3) 数値は改正法と合っています。満たしています。\n(5) 書式は適切です。"
    assert failed_items(ex) == {}
