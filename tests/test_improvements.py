"""改善課題（想定ユーザーでの確認_1105.md）を直したところのテスト。API は呼ばない。"""

import re

from core.draft import Amendment, Draft
from tests.test_partial import board_work  # noqa: F401  (pytest の fixture)


def _ident(c, wid):
    return re.search(r'name="ident" value="([^"]+)"', c.get(f"/works/{wid}/articles").text).group(1)


def test_reason_can_be_edited_and_kept_on_redraft(board_work):
    """変更の理由を画面で書き直せる。AI の元の理由は残り、空にすると戻る。作り直しても残る。"""
    M, store, c, wid, _, _ = board_work
    page = c.get(f"/works/{wid}/articles").text
    assert 'name="reason_規約|第47条"' in page
    original = store.load(wid)["draft"]["amendments"][0]["reason"]
    r = c.post(f"/works/{wid}/articles", data={"ident": _ident(c, wid), "reason_規約|第47条": "委員会で書き直した理由"}, follow_redirects=False)
    assert r.status_code == 303
    w = store.load(wid)
    assert w["draft"]["amendments"][0]["reason"] == "委員会で書き直した理由"
    assert w["human_reasons"]["規約|第47条"]["original"] == original
    assert "human_edits" not in w or "規約|第47条" not in (w.get("human_edits") or {})   # 文を直した印は付けない
    page = c.get(f"/works/{wid}/articles").text
    assert "委員会で書き直した理由" in page and "AI が書いた理由を見る" in page
    # 作り直しても残る
    d = M._draft(w)
    d.amendments[0].reason = "AI の新しい理由"
    M._keep_human_edits(w, d)
    assert d.amendments[0].reason == "委員会で書き直した理由"
    # 空にすると AI の理由に戻る
    c.post(f"/works/{wid}/articles", data={"ident": _ident(c, wid), "reason_規約|第47条": ""})
    w = store.load(wid)
    assert w["draft"]["amendments"][0]["reason"] == original and "規約|第47条" not in w.get("human_reasons", {})


def test_deleted_articles_are_listed_read_only(board_work):
    M, store, c, wid, _, _ = board_work
    w = store.load(wid)
    w["draft"]["amendments"].append(Amendment("削除", "第3条", "第3条", "使用者の資格", "", "使わなくなったため削除", ["other"], [], [],
                                              document="規約").to_dict())
    store.update(wid, draft=w["draft"])
    page = c.get(f"/works/{wid}/articles").text
    assert "この条は削除します" in page and 'name="text_規約|第3条"' not in page and 'name="reason_規約|第3条"' in page


def test_definitions_found_for_edit_check():
    """直した文の確認に、今の規約で言葉を定義している条を渡す（推測で書いて人に確認を頼ませない）。"""
    import app.main as M
    from core.corpus import Corpus
    from core.ingest import load_kiyaku

    corpus = Corpus(load_kiyaku(M.SAMPLE))
    defs = M._definitions(corpus, "対象物件の管理")
    assert defs and all(d["source"] == "今の規約" for d in defs) and "対象物件" in defs[0]["text"]
    assert M._definitions(corpus, "関係のない文") == []


def test_explain_tier_follows_item_topics():
    from core.explain import ExplainItem, Explanation, mark_required

    draft = Draft([Amendment("改正", "第45条", "第45条", "c", "第45条　…", "", ["2-1", "5"], [], [])], "n")
    ex = Explanation(title="t", intro="i", choices=[], resolution="r", closing="c", items=[
        ExplainItem(title="国内管理人", articles=["第45条"], required=True, tier="法律の改正に合わせる変更", what="w", why="y", impact="i",
                    finding_refs=["5"]),
        ExplainItem(title="招集通知", articles=["第45条"], required=False, tier="暮らしや運営に関わる変更", what="w", why="y", impact="i",
                    finding_refs=["2-1"]),
    ])
    mark_required(ex, draft)
    assert [(i.title, i.required) for i in ex.items] == [("招集通知", True), ("国内管理人", False)]


def test_bulk_only_open_keeps_individual_decisions(board_work):
    M, store, c, wid, _, _ = board_work
    findings = [dict(M.store.load(wid)["findings"][0], category="推奨", topic_id="10"),
                dict(M.store.load(wid)["findings"][0], category="推奨", topic_id="11")]
    store.update(wid, findings=findings, decisions={"0": {"decision": "不採用", "reason": "個別に決めた"}, "1": {"decision": "保留", "reason": ""}})
    c.post(f"/works/{wid}/decisions/bulk", data={"scope": "推奨", "decision": "採用", "only_open": "1"})
    d = store.load(wid)["decisions"]
    assert d["0"]["decision"] == "不採用" and d["1"]["decision"] == "採用"


def test_taisho_has_mobile_cards_and_back_link():
    import app.main as M
    from core.corpus import Corpus
    from core.ingest import load_kiyaku
    from core.taisho import to_html

    page = to_html(Draft([Amendment("改正", "第47条", "第47条", "c", "第47条　…", "r", ["1-1"], [], [])], "n"), Corpus(load_kiyaku(M.SAMPLE)))
    assert 'table class="taisho"' in page and 'data-label="現行"' in page and "← 作業の画面に戻る" in page
    assert "table.taisho td::before" in page


def test_step5_shows_explanation_and_folds_metrics(board_work):
    M, store, c, wid, _, _ = board_work
    store.update(wid, explain={"title": "改正のご説明", "intro": "法律が変わりました。", "items": [
        {"title": "総会の決め方が変わります", "articles": ["第47条"], "required": True, "tier": "法律の改正に合わせる変更",
         "what": "w", "why": "y", "impact": "i"}], "choices": [], "resolution": "r", "closing": "c"},
        explain_metrics={"1文の平均の長さ": 38.0, "60字を超える文の割合(%)": 8.0, "説明なしの専門用語": []})
    page = c.get(f"/works/{wid}").text
    assert "法律が変わりました。" in page and "総会の決め方が変わります" in page and "読みやすさの目安（作る側向け）" in page


def test_top_links_and_user_facing_words():
    from fastapi.testclient import TestClient

    import app.main as M

    page = TestClient(M.app).get("/").text
    assert 'href="#samples"' in page and 'id="samples"' in page
    assert "GitHub" not in page and "private/" not in page
