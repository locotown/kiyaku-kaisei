"""指摘の見せ方（論点名・条の見出し・根拠の本文）と、判断の保存後の案内のテスト。API は呼ばない。"""

import shutil

from core.present import annotate, view

FINDING = {"article": "規定なし", "topic_id": "9", "category": "推奨", "issue": "i", "current_excerpt": "",
           "law_basis": ["第46条の2"], "standard_basis": ["第67条の4", "第46条第7項"], "where": "規約",
           "proposal": "標準管理規約にならい第67条の4・第67条の5を新設し、議決権行使（第46条）も定める。区分所有法第31条第1項による。",
           "document": "規約"}


def test_view_and_annotate():
    v = view(FINDING)
    assert v["title"] == "マンションに特化した財産管理制度"
    assert "定めがありません" in v["target"]
    html = str(annotate(FINDING["proposal"], FINDING))
    assert "第67条の4<span class=\"refcap\">〔所有者不明専有部分管理命令" in html
    assert "第46条<span class=\"refcap\">〔議決権〕" in html
    assert "<span" not in str(annotate("第47条（総会の会議及び議事）を改める", FINDING))  # 直後に（…）があれば添えない
    assert "第31条第1項<span class=\"refcap\">〔規約の設定、変更及び廃止〕" in html
    law, std = v["basis"][0], v["basis"][1]
    assert law["source"] == "区分所有法" and law["caption"] == "所有者不明専有部分管理命令" and "裁判所" in law["text"]
    assert std["source"] == "標準管理規約" and std["text"]


def test_save_shows_next_step():
    from fastapi.testclient import TestClient

    import app.main as M
    from app import store

    wid = store.new_id()
    d = store.path(wid)
    d.mkdir(parents=True)
    shutil.copy(M.SAMPLE, d / "source.txt")
    store.save(wid, {"name": "t", "info": {"型": "単棟型"}, "status": "点検済み", "articles": 87, "log": [],
                     "findings": [FINDING], "decisions": {"0": {"decision": "保留", "reason": ""}}})
    try:
        c = TestClient(M.app)
        r = c.post(f"/works/{wid}/decisions", data={"decision_0": "採用"}, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].endswith("?saved=1#next")
        page = c.get(r.headers["location"]).text
        assert "判断を保存しました" in page and "採用した指摘から改定案を作る" in page
        assert "マンションに特化した財産管理制度" in page
        store.update(wid, draft={"amendments": [], "notes": ""})
        c.post(f"/works/{wid}/decisions", data={"decision_0": "不採用"})
        assert store.load(wid)["draft_stale"] is True
        assert "改定案を作り直す" in c.get(f"/works/{wid}").text
    finally:
        shutil.rmtree(d)
