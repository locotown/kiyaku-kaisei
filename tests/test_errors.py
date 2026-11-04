"""エラーは、画面では日本語のページで示す（{"detail": ...} をそのまま見せない）。"""

from fastapi.testclient import TestClient

from app.main import app

HTML = {"accept": "text/html,application/xhtml+xml"}


def test_missing_work_is_404_page():
    c = TestClient(app)
    r = c.get("/works/20990101-000000-000000", headers=HTML)
    assert r.status_code == 404
    assert "この作業は見つかりません" in r.text and "トップに戻る" in r.text
    r = c.get("/works/../etc", headers=HTML)
    assert r.status_code == 404


def test_upload_without_file_shows_japanese_page():
    c = TestClient(app)
    r = c.post("/works", data={"name": "テスト", "kind": "単棟型"}, headers=HTML)
    assert r.status_code == 400
    assert "規約のファイルを選んでください" in r.text and '"detail"' not in r.text
    r = c.post("/works", data={"kind": "単棟型"}, headers=HTML)  # 名前がない
    assert r.status_code == 400 and "入力が足りない" in r.text


def test_api_calls_still_get_json():
    c = TestClient(app)
    r = c.get("/works/20990101-000000-000000/status")
    assert r.status_code == 404 and "detail" in r.json()


def test_bulk_decisions(tmp_path, monkeypatch):
    import json

    from app import store

    monkeypatch.setattr(store, "WORK", tmp_path)
    wid = "20990101-000000-aaaaaa"
    findings = [{"category": c, "article": "第1条", "topic_id": "x", "issue": "", "proposal": "", "basis": [],
                 "current_excerpt": "", "document": "規約"} for c in ("必須", "推奨", "推奨", "参考")]
    store.save(wid, {"name": "t", "info": {}, "status": "点検済み", "findings": findings, "log": [],
                     "decisions": {str(i): {"decision": "採用" if i == 0 else "保留", "reason": ""} for i in range(4)}})
    c = TestClient(app)
    r = c.post(f"/works/{wid}/decisions/bulk", data={"scope": "推奨", "decision": "採用"})
    assert r.json()["changed"] == 2
    d = json.loads((tmp_path / wid / "work.json").read_text(encoding="utf-8"))["decisions"]
    assert [d[str(i)]["decision"] for i in range(4)] == ["採用", "採用", "採用", "保留"]
    assert d["1"]["reason"] == "まとめて採用" and len(d["1"]["history"]) == 1
    # 必須は範囲に入らない。同じ判断なら変えない
    assert c.post(f"/works/{wid}/decisions/bulk", data={"scope": "推奨・参考", "decision": "採用"}).json()["changed"] == 1
    assert c.post(f"/works/{wid}/decisions/bulk", data={"scope": "必須", "decision": "保留"}).status_code == 400


def test_word_downloads_need_documents(monkeypatch, tmp_path):
    """Word の資料は、元の資料ができていなければ 404（分かりやすいページ）。"""
    import json

    from fastapi.testclient import TestClient

    from app import main as M
    from app import store

    monkeypatch.setattr(store, "WORK", tmp_path)
    (tmp_path / "20261104-000020-aaaaaa").mkdir()
    (tmp_path / "20261104-000020-aaaaaa" / "work.json").write_text(json.dumps({"name": "試験", "status": "点検済み"}), encoding="utf-8")
    c = TestClient(M.app)
    for doc in ("taisho", "board", "explain"):
        r = c.get(f"/works/20261104-000020-aaaaaa/{doc}.docx", headers={"accept": "text/html"})
        assert r.status_code == 404 and "まだありません" in r.text
