"""検証ループ L1：標準どおりの条は、国の改正文を下書きにする。"""

from core.findings import Finding
from core.ingest import load_kiyaku
from core.precedent import standard_before, standard_drafts, to_prompt


def F(article, topic="1-1", basis=("第47条第3項",), document="規約"):
    return Finding(document=document, article=article, topic_id=topic, category="必須", issue="", current_excerpt="",
                   law_basis=[], standard_basis=list(basis), where="", proposal="")


def test_standard_rules_get_national_text():
    r = standard_drafts(standard_before(), [F("第47条"), F("規定なし", "4", ("第67条の3",))])
    assert r["standard_like"] and r["ratio"] == 1.0
    arts = {d["article"]: d for d in r["drafts"]}
    assert arts["第47条"]["kind"] == "改正" and "4分の3" in arts["第47条"]["text"]
    assert arts["第67条の3"]["kind"] == "新設"
    p = to_prompt(r)
    assert "国の改正文（下書き）" in p and "採用した指摘（と理事会の判断）に当たる部分だけ" in p


def test_renumbered_rules_are_not_used(tmp_path):
    # 条番号が標準と違う規約（架空）では、国の文の参照がずれるので下書きにしない
    k = load_kiyaku("evals/data/old_style_kiyaku.txt")
    r = standard_drafts(k, [F("第45条"), F("規定なし", "4", ("第67条の3",))])
    assert not r["standard_like"]
    assert all(d["article"] != "第67条の3" for d in r["drafts"])


def test_rules_and_unchanged_articles_are_skipped():
    r = standard_drafts(standard_before(), [F("第1条", basis=()), F("第3条", document="駐車場使用細則", basis=())])
    assert r["drafts"] == []  # 第1条は国の改正で変わっていない。細則は対象外
    assert to_prompt(r) == ""
