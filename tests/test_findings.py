"""指摘の検証（根拠を示せない指摘は出さない）とカスタムツールのテスト。API は呼ばない。"""

import json
from pathlib import Path

import pytest

from core.findings import validate
from core.ingest import load_kiyaku
from core.sources import law, normalize_article_ref
from core.tools import ToolHandler

ROOT = Path(__file__).resolve().parents[1]
BEFORE = ROOT / "evals/data/r7_tantou_before.txt"


@pytest.fixture(scope="module")
def kiyaku():
    return load_kiyaku(BEFORE)


def base(**kw):
    f = {
        "article": "第47条",
        "topic_id": "1-2",
        "category": "必須",
        "issue": "特別決議の定足数が改正法に合っていない。",
        "current_excerpt": "議決権総数の半数以上を有する組合員が出席しなければならない。",
        "law_basis": ["第31条第1項"],
        "standard_basis": ["第47条第3項"],
        "where": "規約",
        "proposal": "定足数を組合員総数・議決権総数の各過半数にする。",
    }
    f.update(kw)
    return f


def test_normalize_article_ref():
    assert normalize_article_ref("第31条第1項") == "31"
    assert normalize_article_ref("第六条の二") == "6の2"
    assert normalize_article_ref("区分所有法第38条の2") == "38の2"


def test_law_has_new_articles():
    assert "38の2" in law()  # 所在等不明区分所有者の除外（令和7年改正で新設）
    assert "国内管理人" in law()["6の2"]


def test_accepts_grounded_finding(kiyaku):
    finding, _ = validate(base(), kiyaku)
    assert finding is not None
    assert finding.category == "必須"


def test_rejects_without_basis(kiyaku):
    finding, errors = validate(base(law_basis=[], standard_basis=[]), kiyaku)
    assert finding is None
    assert "根拠" in errors[0]


def test_rejects_unknown_law_article(kiyaku):
    finding, _ = validate(base(law_basis=["第999条"]), kiyaku)
    assert finding is None


def test_rejects_fabricated_quote(kiyaku):
    finding, errors = validate(base(current_excerpt="組合員の3分の1以上が出席すれば足りる。"), kiyaku)
    assert finding is None
    assert any("引用" in e for e in errors)


def test_rejects_unknown_article(kiyaku):
    finding, _ = validate(base(article="第200条"), kiyaku)
    assert finding is None


def test_allows_missing_provision(kiyaku):
    finding, _ = validate(base(article="規定なし", topic_id="5", category="推奨", current_excerpt="",
                               law_basis=["第6条の2"], standard_basis=["第31条の3"]), kiyaku)
    assert finding is not None


def test_category_follows_topic_table(kiyaku, monkeypatch):
    finding, warnings = validate(base(category="推奨"), kiyaku)
    assert finding.category == "必須"
    assert warnings
    # 1-4〜1-6 は 11/3 に必須へ（docs/DOMAIN.md）
    finding, _ = validate(base(topic_id="1-6", category="推奨"), kiyaku)
    assert finding.category == "必須" and not finding.needs_confirmation
    # 「要確認」の論点は推奨として扱い、要確認の印を付ける（いまは該当がないので、論点表を一時的に書き換えて確かめる）
    from core.topics import TOPIC_BY_ID
    monkeypatch.setitem(TOPIC_BY_ID, "1-4", {**TOPIC_BY_ID["1-4"], "category": "要確認"})
    finding, _ = validate(base(topic_id="1-4", category="必須"), kiyaku)
    assert finding.category == "推奨" and finding.needs_confirmation


def test_other_topic_needs_law_for_required(kiyaku):
    finding, _ = validate(base(topic_id="other", category="必須", law_basis=[]), kiyaku)
    assert finding is None


def test_tool_handler(kiyaku):
    h = ToolHandler(kiyaku)
    listing = json.loads(h.run("list_articles", {}))
    assert listing["条の数"] == 87
    assert "半数以上" in h.run("get_articles", {"articles": ["47"]})
    assert "保険金等" in h.run("get_standard_articles", {"articles": ["第24条の2"]})
    assert "ありません" in h.run("get_articles", {"articles": ["第24条の2"]})
    out = json.loads(h.run("record_findings", {"findings": [base(), base(law_basis=[], standard_basis=[])]}))
    assert len(out["受け付けた指摘"]) == 1 and len(out["受け付けなかった指摘"]) == 1
    assert len(h.findings) == 1
