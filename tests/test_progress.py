"""処理中の進み具合の表示のテスト。API は呼ばない。"""

import shutil

from core.progress import describe_builtin, describe_tool, summarize


def test_describe_and_summarize():
    assert describe_tool("get_articles", {"articles": ["第45条", "第47条"]}) == "get_articles：規約の条文を確認：第45条・第47条"
    assert describe_tool("get_rule_articles", {"rule": "駐車場使用細則", "articles": ["第1条"]}).endswith("駐車場使用細則 第1条")
    assert "ほか2件" in describe_tool("get_law_articles", {"articles": ["31", "17", "35", "39", "61", "62"]})
    assert describe_builtin("read") == "read：手順書を読む"
    log = [{"kind": "builtin", "text": describe_builtin("read")},
           {"kind": "tool", "text": describe_tool("get_articles", {"articles": ["第47条"]})},
           {"kind": "tool", "text": describe_tool("get_standard_articles", {"articles": ["第47条"]})}]
    p = summarize("点検中", log)
    assert p["stage"] == 2 and p["counts"]["規約の条"] == 1 and p["counts"]["標準管理規約"] == 1 and p["estimate"]
    log += [{"kind": "tool", "text": describe_tool("record_findings", {"findings": [{}, {}]})},
            {"kind": "found", "text": "指摘を2件受け付け（合計7件）"}]
    p = summarize("点検中", log)
    assert p["stage"] == 3 and p["counts"]["指摘"] == 7
    assert summarize("改定案作成中", [{"kind": "graded", "text": "satisfied"}])["stage"] == 4


def test_status_progress():
    from fastapi.testclient import TestClient

    import app.main as M
    from app import store

    wid = store.new_id()
    d = store.path(wid)
    d.mkdir(parents=True)
    shutil.copy(M.SAMPLE, d / "source.txt")
    store.save(wid, {"name": "t", "info": {"型": "単棟型"}, "status": "点検中", "articles": 87, "log": []})
    try:
        store.append_log(wid, "session", "sesn_xxx")
        store.append_log(wid, "tool", describe_tool("get_articles", {"articles": ["第47条"]}))
        c = TestClient(M.app)
        p = c.get(f"/works/{wid}/status").json()["progress"]
        assert p["current"] == "規約の条文を確認：第47条" and p["lines"][0]["text"] == "AI の作業を始めました"
        assert p["stage"] == 1 and p["elapsed"] >= 0 and p["last_age"] >= 0
        page = c.get(f"/works/{wid}").text
        assert "経過時間" in page and "目安 3〜7分" in page and "規約を読む" in page
        store.update(wid, status="点検済み")
        assert c.get(f"/works/{wid}/status").json()["progress"] is None
    finally:
        shutil.rmtree(d)


def test_journey_and_done_banner():
    from app.main import journey

    j = journey({"status": "点検済み", "findings": [{}]}, None)
    assert [st["state"] for st in j["steps"]] == ["done", "now", "todo", "todo", "todo", "todo"] and "判断" in j["next"]
    j = journey({"status": "改定案あり", "findings": [{}], "draft": {"amendments": []}, "draft_stale": True}, None)
    assert j["current"] == "draft" and "作り直す" in j["next"]
    j = journey({"status": "改定案作成中", "findings": [{}]}, None)
    assert j["current"] == "draft" and "AI が作業" in j["next"]
    j = journey({"status": "説明文あり", "findings": [{}], "draft": {"amendments": []}, "explain": {"items": []}}, {"ready": True})
    assert j["current"] == "meeting" and "総会が終わったら" in j["next"]
    j = journey({"status": "説明文あり", "findings": [{}], "draft": {"amendments": []}, "explain": {"items": []},
                 "meeting": {"results": {"規約": "可決"}}}, {"ready": True})
    assert j["current"] == "" and all(st["state"] == "done" for st in j["steps"])


def test_draft_plan_scales_with_adopted():
    from core.progress import draft_plan, summarize

    assert draft_plan(7)["deadline_min"] == 30 and not draft_plan(7)["large"]
    assert draft_plan(21)["deadline_min"] > 30 and draft_plan(21)["budget_usd"] > 5 and draft_plan(21)["large"]
    assert summarize("改定案作成中", [], adopted=21)["estimate"] == draft_plan(21)["estimate"]
