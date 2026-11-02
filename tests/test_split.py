from pathlib import Path

import pytest

from core.ingest import load_kiyaku
from core.split import article_number, kanji_to_int, split_kiyaku

ROOT = Path(__file__).resolve().parents[1]
STANDARD_PDF = ROOT / "data/public/mlit/r7_hyojun_kiyaku_tantou.pdf"


def test_kanji_to_int():
    assert kanji_to_int("一") == 1
    assert kanji_to_int("十二") == 12
    assert kanji_to_int("二十") == 20
    assert kanji_to_int("百二十三") == 123
    assert kanji_to_int("47") == 47


def test_article_number():
    assert article_number("47", "") == "47"
    assert article_number("24", "の2") == "24の2"
    assert article_number("六十七", "の三") == "67の3"
    assert article_number("31", " の 2") == "31の2"


def test_basic_structure():
    k = split_kiyaku([
        "第１章　総則",
        "（目的）",
        "第１条　この規約は、",
        "目的とする。",  # 改行で途切れた文はつなげる
        "（総会の会議及び議事）",
        "第47条　総会の会議は、",
        "２　総会の議事は、出席組合員の議決権の過半数で決する。",
        "３　次の各号に掲げる事項に関する総会の議事は、",
        "一　規約の制定、変更又は廃止",
        "二　敷地及び共用部分等の変更",
        "イ　細分",
    ])
    assert [a.number for a in k.articles] == ["1", "47"]
    a1 = k.find("1")
    assert a1.caption == "目的"
    assert a1.chapter == "第1章　総則"
    assert a1.paragraphs[0].text == "この規約は、目的とする。"
    a47 = k.find("47")
    assert [p.num for p in a47.paragraphs] == [1, 2, 3]
    assert len(a47.paragraphs[2].items) == 2
    assert a47.paragraphs[2].items[1].endswith("イ　細分")


def test_inline_caption():
    k = split_kiyaku(["第1条（目的）　この規約は、目的とする。"])
    assert k.find("1").caption == "目的"
    assert k.find("1").paragraphs[0].text == "この規約は、目的とする。"


def test_variants():
    k = split_kiyaku([
        "〔※電磁的方法の利用状況に応じて、次のように規定〕",
        "（ア）利用可能ではない場合",
        "（届出義務）",
        "第31条　書面により届け出る。",
        "（イ）利用可能な場合",
        "（届出義務）",
        "第31条　書面又は電磁的方法により届け出る。",
        "（業務）",
        "第32条　管理組合は、",
    ])
    assert k.keys() == ["31(ア)", "31(イ)", "32"]
    assert k.find("31", "ア").note.startswith("〔※")
    assert k.find("32").variant is None
    assert k.find("32").note == ""


def test_appendix_is_separated():
    k = split_kiyaku(["第72条　最後の条。", "附　則", "第1条　この規約は、○年○月○日から効力を発する。"])
    assert [a.number for a in k.articles] == ["72"]
    assert k.appendix[0].startswith("附")


@pytest.mark.skipif(not STANDARD_PDF.exists(), reason="標準管理規約のPDFがない")
def test_standard_pdf():
    """令和7年改正の標準管理規約（単棟型）PDF：第1条〜第72条と枝番12条、選択式を含め94条。"""
    k = load_kiyaku(STANDARD_PDF)
    numbers = list(dict.fromkeys(a.number for a in k.articles))
    assert len(k.articles) == 94
    assert len(numbers) == 84
    assert numbers[0] == "1" and numbers[-1] == "72"
    a47 = k.find("47")
    assert a47.paragraphs[0].text.endswith("出席しなければならない。")
    assert "組合員総数の過半数であって議決権総数の過半数" in a47.paragraphs[2].text
