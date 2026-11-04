"""見え消しから作る正解データの検証。"""

from pathlib import Path

import pytest

from core.split import split_kiyaku
from evals.build_r7_gold import SRC, attach_topics, compare, read_redline

pytestmark = pytest.mark.skipif(not Path(SRC).exists(), reason="見え消しの docx がない")


@pytest.fixture(scope="module")
def parsed():
    before_lines, after_lines = read_redline(SRC)
    return split_kiyaku(before_lines), split_kiyaku(after_lines)


def test_article_counts(parsed):
    before, after = parsed
    assert len(before.articles) == 87
    assert len(after.articles) == 94
    numbers = list(dict.fromkeys(a.number for a in after.articles))
    assert numbers[0] == "1" and numbers[-1] == "72"


def test_old_and_new_wording(parsed):
    before, after = parsed
    assert "半数以上" in before.find("47").paragraphs[0].text
    assert "過半数" in after.find("47").paragraphs[0].text
    assert "組合員総数の４分の３以上".replace("４", "4").replace("３", "3") in before.find("47").paragraphs[2].text


def test_changes(parsed):
    changes = compare(*parsed)
    attach_topics(changes)
    by_key = {c["key"]: c for c in changes if c["key"]}
    # 新設
    for key in ["24の2", "31の3(ア)", "32の2", "67の3", "67の4", "67の5"]:
        assert by_key[key]["change"] == "新設", key
    # 第64条の2（組合員名簿等）は第31条の2へ移動（参照先の書き換えあり）
    assert by_key["31の2(ア)"]["before_key"] == "64の2(ア)"
    assert by_key["31の2(ア)"]["change"].startswith("移動")
    # 必須の論点を含む条
    assert by_key["47"]["category"] == "必須"
    assert by_key["43"]["category"] == "必須"
    assert by_key["24の2"]["category"] == "必須"
    # 変更のない条は含まれない
    assert "1" not in by_key
