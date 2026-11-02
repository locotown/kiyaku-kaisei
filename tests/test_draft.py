"""改定案の検査と新旧対照表のテスト。API は呼ばない。"""

from pathlib import Path

import pytest

from core.draft import check
from core.findings import validate
from core.ingest import load_kiyaku
from core.taisho import rows, to_html, to_markdown

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def kiyaku():
    return load_kiyaku(ROOT / "evals/data/r7_tantou_before.txt")


@pytest.fixture(scope="module")
def findings(kiyaku):
    f, _ = validate({
        "article": "第43条", "topic_id": "2-2", "category": "必須", "issue": "緊急招集の期間が短すぎる。",
        "current_excerpt": "５日間を下回らない範囲において".replace("５", "5"),
        "law_basis": ["第35条第1項"], "standard_basis": ["第43条第8項"], "where": "規約", "proposal": "1週間にする。",
    }, kiyaku)
    assert f is not None
    return [f]


def amendment(kiyaku, **kw):
    current = kiyaku.find("43").text().split("\n", 1)[1]  # 見出しの行を除く
    a = {
        "kind": "改正", "article": "第43条", "before_article": "第43条", "caption": "招集手続",
        "text": current.replace("5日間を下回らない", "1週間を下回らない"),
        "reason": "改正法で、招集通知は1週間より短くできなくなりました。",
        "finding_refs": ["2-2"], "law_basis": ["第35条第1項"], "standard_basis": ["第43条第8項"],
    }
    a.update(kw)
    return a


def test_check_accepts_valid_draft(kiyaku, findings):
    draft, errors, _ = check({"amendments": [amendment(kiyaku)], "notes": "総会提案の下書きであり、法的助言ではありません。"}, kiyaku, findings)
    assert errors == []
    assert draft.amendments[0].article == "第43条"


def test_check_requires_all_required_topics(kiyaku, findings):
    _, errors, _ = check({"amendments": [amendment(kiyaku, finding_refs=[])], "notes": "法的助言ではありません"}, kiyaku, findings)
    assert any("2-2" in e for e in errors)


def test_check_rejects_new_article_that_exists(kiyaku, findings):
    bad = amendment(kiyaku, kind="新設", before_article=None)
    _, errors, _ = check({"amendments": [bad], "notes": "法的助言ではありません"}, kiyaku, findings)
    assert any("すでにあります" in e for e in errors)


def test_check_rejects_text_without_article_head(kiyaku, findings):
    _, errors, _ = check({"amendments": [amendment(kiyaku, text="理事長は…")], "notes": "法的助言ではありません"}, kiyaku, findings)
    assert any("から始めて" in e for e in errors)


def test_taisho_marks_only_changes(kiyaku, findings):
    draft, _, _ = check({"amendments": [amendment(kiyaku), {
        "kind": "新設", "article": "第24条の2", "before_article": None, "caption": "保険金等の請求及び受領等",
        "text": "第24条の2　理事長は、保険金等の請求及び受領について、区分所有者を代理する。",
        "reason": "新設", "finding_refs": [], "law_basis": ["第26条第2項"], "standard_basis": ["第24条の2"],
    }], "notes": "法的助言ではありません"}, kiyaku, findings)
    r = rows(draft, kiyaku)
    changed_new = "".join(t for t, c in r[0]["new"] if c)
    changed_old = "".join(t for t, c in r[0]["old"] if c)
    assert "1週間" in changed_new and "5日間" in changed_old
    assert "総会を招集するには" not in changed_new  # 変えていない部分に下線を引かない
    assert r[1]["old"] == [("（新設）", False)]
    html = to_html(draft, kiyaku)
    assert "<mark>1週間</mark>" in html and "<del>5日間</del>" in html and "法的助言ではありません" in html
    assert "（新設）" in to_markdown(draft, kiyaku)
