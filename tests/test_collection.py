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
