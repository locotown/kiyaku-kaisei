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
    # 印刷：A4 横、各ページに資料名とページ番号。画面には「印刷する」「Word で保存」
    assert "size: A4 landscape" in html and "counter(pages)" in html and 'href="taisho.docx"' in html


def test_taisho_docx(kiyaku, findings):
    """新旧対照表の Word：A4 横、表の見出しを各ページにくり返す、変えた語句に下線・取り消し線。"""
    import io

    from docx import Document

    from core.wordout import taisho_docx

    draft, _, _ = check({"amendments": [amendment(kiyaku)], "notes": "法的助言ではありません"}, kiyaku, findings)
    doc = Document(io.BytesIO(taisho_docx(draft, kiyaku, "試験 新旧対照表（案）")))
    sec = doc.sections[0]
    assert sec.page_width > sec.page_height                       # 横
    assert "総会提案の下書き" in sec.header.paragraphs[0].text
    t = doc.tables[0]
    assert [c.text for c in t.rows[0].cells] == ["改定案", "現行", "区分・変更の理由・根拠"]
    assert t.rows[0]._tr.xpath("./w:trPr/w:tblHeader")             # 見出しの行をくり返す
    new_runs, old_runs = t.rows[1].cells[0].paragraphs[0].runs, t.rows[1].cells[1].paragraphs[0].runs
    assert any(r.text == "1週間" and r.font.underline for r in new_runs)
    assert any(r.text == "5日間" and r.font.strike for r in old_runs)
    assert not any("総会を招集するには" in r.text and r.font.underline for r in new_runs)


def test_notes_sections():
    from core.taisho import notes_sections

    secs = notes_sections("総会提案の下書きです。\n【決議の進め方】改正法の要件で決議する。\n【組合が選ぶ点】電磁的方法の利用。")
    assert secs[0] == ("", "総会提案の下書きです。")
    assert secs[1] == ("決議の進め方", "改正法の要件で決議する。")
    assert secs[2][0] == "組合が選ぶ点"
    assert notes_sections("見出しなし") == [("", "見出しなし")]


def test_readability():
    from core.readability import measure

    m = measure(["特別決議（大事なことを決める方法）が変わります。定足数が変わります。"])
    assert m["文の数"] == 2
    assert "特別決議" not in m["説明なしの専門用語"]
    assert "定足数" in m["説明なしの専門用語"]


def test_classify_required_and_optional():
    from core.draft import Amendment
    from core.taisho import classify

    a = Amendment(kind="改正", article="第47条", before_article="第47条", caption="", text="第47条　…", reason="",
                  finding_refs=["1-1", "1-3"], law_basis=[], standard_basis=["第47条"])
    c = classify(a)
    assert c["is_required"] and c["required"] == ["特別決議を出席者の多数決に"]
    assert c["optional"] == ["普通決議の定足数"]
    b = Amendment(kind="改正", article="第20条", before_article="第20条", caption="", text="第20条　…", reason="",
                  finding_refs=["10"], law_basis=[], standard_basis=["第20条"])
    assert not classify(b)["is_required"]


def test_explanation_tiers_and_coverage():
    from core.draft import Amendment, Draft
    from core.explain import ExplainItem, Explanation, coverage, mark_required, to_html

    draft = Draft([
        Amendment("改正", "第47条", "第47条", "総会の会議及び議事", "第47条　…", "", ["1-1"], [], ["第47条"]),
        Amendment("改正", "第20条", "第20条", "区分所有者の責務", "第20条　…", "", ["10"], [], ["第20条"]),
        Amendment("改正", "第48条", "第48条", "議決事項", "第48条　…", "", ["other"], [], ["第48条"]),
    ], "法的助言ではありません")
    item = lambda title, arts, tier: ExplainItem(title=title, articles=arts, required=False, tier=tier, what="", why="", impact="")
    ex = Explanation(title="t", intro="", choices=[], resolution="", closing="", items=[
        item("責務", ["第20条"], "法律の改正に合わせる変更"),  # AI が誤って①にしても、必須の論点がなければ②に直す
        item("総会", ["第47条"], "暮らしや運営に関わる変更"),  # 必須の論点を含むので①に直す
    ])
    mark_required(ex, draft)
    assert [i.title for i in ex.items] == ["総会", "責務"]
    assert ex.items[0].tier == "法律の改正に合わせる変更" and ex.items[1].tier == "暮らしや運営に関わる変更"
    assert coverage(ex, draft)["missing"] == ["第48条"]
    assert "本文では取り上げていません" in to_html(ex, "", draft)
