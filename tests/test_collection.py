"""規約集を文書ごとに分ける処理のテスト（架空の規約集を使う）。"""

from pathlib import Path

import pytest

from core.collection import classify_title, clean_line, segment
from core.ingest import load_kiyaku
from core.split import split_kiyaku

SAMPLE = Path(__file__).parent / "fixtures/kiyakushu_sample.txt"


@pytest.fixture(scope="module")
def collection():
    return segment(SAMPLE.read_text(encoding="utf-8").splitlines())


def test_documents(collection):
    kinds = [(d.kind, d.title) for d in collection.documents]
    assert kinds == [
        ("メモ", "○○マンション　管理規約・細則"),
        ("規約", "○○マンション管理規約"),
        ("細則", "○○マンション使用細則"),
        ("細則", "○○マンション駐車場使用細則"),
        ("改正履歴", "規約の改正履歴(判明している範囲)"),
    ]


def test_main_rules(collection):
    k = collection.main.kiyaku
    assert [a.label for a in k.articles] == ["第1条", "第2条", "第3条", "第4条", "第5条"]
    a4 = k.find("4")
    assert [p.num for p in a4.paragraphs] == [1, 2, 3]  # 「2．」形式の項
    assert len(a4.paragraphs[2].items) == 2  # 「(1)」形式の号
    assert "規約集" not in k.find("1").text()  # ページ参照を取り除く
    assert k.appendix[0].startswith("附")  # 附則・別表は規約本体の付録


def test_annotations_are_separated(collection):
    main = collection.main
    assert any(x.startswith("◆") for x in main.annotations)
    assert any(x.startswith("★") for x in main.annotations)
    assert all("★" not in a.text() and "◆" not in a.text() for a in main.kiyaku.articles)
    assert collection.documents[0].annotations[0].startswith("- 反映範囲")


def test_rules_styles(collection):
    use, parking = collection.rules
    assert use.style == "項目" and [a.label for a in use.kiyaku.articles] == ["1.", "2."]
    assert len(use.kiyaku.find("2").paragraphs[0].items) == 2
    assert parking.style == "条" and len(parking.kiyaku.articles) == 3
    assert [p.num for p in parking.kiyaku.find("2").paragraphs] == [1, 2]


def test_title_rules():
    assert classify_title("○○マンション管理規約") == "規約"
    assert classify_title("○○マンション使用細則") == "細則"
    assert classify_title("窓ガラス等の工事に関する細則 (2026-11-01 追加)") == "細則"
    assert classify_title("○○マンション 管理規約・細則") == "メモ"
    assert classify_title("細則の改正履歴") == "改正履歴"
    assert classify_title("細則 駐車場使用細則 全面改定 第3号議案") is None  # 表の行は題名にしない
    assert classify_title("★ 別紙の改訂履歴と食い違い") is None  # 注記は題名にしない
    assert clean_line("第1条(目的)  (規約集 p11)") == "第1条(目的)"


def test_load_kiyaku_returns_main_rules():
    k = load_kiyaku(SAMPLE)
    assert len(k.articles) == 5


def test_paragraph_dot_and_paren_items():
    k = split_kiyaku([
        "第1条 次の各号に掲げる事項は総会で決める。",
        "(1) 規約の変更",
        "(2) 役員の選任",
        "2. 前項の決議は、出席者の過半数で行う。",
        "第2条 次の各号のいずれかに該当する者は、役員になれない。",
        "一 破産者",
        "イ 細分",
        "(1) さらに細分",  # 「イ」の後の「(1)」は細分のまま
    ])
    a1, a2 = k.articles
    assert [p.num for p in a1.paragraphs] == [1, 2] and len(a1.paragraphs[0].items) == 2
    assert len(a2.paragraphs[0].items) == 1 and "(1) さらに細分" in a2.paragraphs[0].items[0]


def _corpus():
    from core.corpus import Corpus

    return Corpus.from_collection(segment(SAMPLE.read_text(encoding="utf-8").splitlines()))


def test_corpus_resolve():
    c = _corpus()
    assert c.resolve("規約") == "規約"
    assert c.resolve("駐車場使用細則") == "○○マンション駐車場使用細則"  # 題名の一部でも引ける
    assert c.resolve("存在しない細則") is None
    assert c.resolution("規約") == "特別決議" and c.resolution("○○マンション駐車場使用細則") == "普通決議"


def test_finding_in_rule():
    from core.findings import validate

    c = _corpus()
    base = {"topic_id": "other", "category": "参考", "issue": "x", "law_basis": [], "standard_basis": ["第18条"],
            "where": "細則で対応可", "proposal": "y"}
    ok, _ = validate(dict(base, document="駐車場使用細則", article="第2条", current_excerpt="使用料は、月額5,000円とする。"), c)
    assert ok is not None and ok.document == "○○マンション駐車場使用細則"
    bad, errors = validate(dict(base, document="駐車場使用細則", article="第9条", current_excerpt=""), c)
    assert bad is None and "駐車場使用細則" in errors[0]
    item, _ = validate(dict(base, document="○○マンション使用細則", article="2.", current_excerpt="居住者は、ごみを所定の場所に出す。"), c)
    assert item is not None  # 項目形式の細則


def test_draft_and_taisho_with_rules():
    from core.draft import check
    from core.taisho import to_html, to_markdown

    c = _corpus()
    data = {"notes": "法的助言ではありません", "amendments": [
        {"document": "規約", "kind": "改正", "article": "第4条", "before_article": "第4条", "caption": "総会の会議及び議事",
         "text": "第4条　総会の会議は、議決権総数の過半数を有する組合員が出席しなければならない。", "reason": "r",
         "finding_refs": ["1-3"], "law_basis": [], "standard_basis": ["第47条"]},
        {"document": "○○マンション使用細則", "kind": "改正", "article": "2.", "before_article": "2.", "caption": "清掃",
         "text": "2.　(1)　共用部分の清掃は、管理会社が行う。", "reason": "r",
         "finding_refs": [], "law_basis": [], "standard_basis": ["第18条"]},
    ]}
    draft, errors, _ = check(data, c, [])
    assert errors == [], errors
    html = to_html(draft, c)
    assert "管理規約の改定案（総会の特別決議）" in html
    assert "○○マンション使用細則の改定案（総会の普通決議）" in html
    assert "<del>管理員</del>" in html  # 細則の現行本文と比べている
    assert "普通決議" in to_markdown(draft, c)
