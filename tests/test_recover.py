"""サーバーの起動時に、処理中のまま止まった作業を「途中で止まった」に切り替える（recover_interrupted）。"""

import json

from app import main as M
from app import store


def _work(tmp_path, wid, **data):
    d = tmp_path / wid
    d.mkdir()
    (d / "work.json").write_text(json.dumps({"name": "試験", **data}, ensure_ascii=False), encoding="utf-8")


def test_recover_interrupted(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "WORK", tmp_path)
    # 今回の処理（status_since 以降）で始めたセッションがある → 途中から再開できる
    _work(tmp_path, "20261104-000001-aaaaaa", status="改定案作成中", status_since=100,
          log=[{"t": "09:00:00", "ts": 50, "kind": "session", "text": "sesn_old"},
               {"t": "10:00:00", "ts": 120, "kind": "session", "text": "sesn_now"},
               {"t": "10:01:00", "ts": 130, "kind": "tool", "text": "条文を読む"}])
    # 前の処理のセッションしかない → 再開できない（古い結果を受け取らないように）
    _work(tmp_path, "20261104-000004-dddddd", status="改定案作成中", status_since=200,
          log=[{"t": "09:00:00", "ts": 50, "kind": "session", "text": "sesn_old"}])
    _work(tmp_path, "20261104-000002-bbbbbb", status="点検中", demo_busy=True)  # デモの録画用は切り替えない
    _work(tmp_path, "20261104-000003-cccccc", status="改定案あり")             # 処理中でないものは触らない

    assert sorted(M.recover_interrupted()) == ["20261104-000001-aaaaaa", "20261104-000004-dddddd"]
    w = store.load("20261104-000001-aaaaaa")
    assert w["status"] == "改定案エラー" and w["interrupted"] == "改定案作成中" and w["interrupted_session"] == "sesn_now"
    assert "途中で止まりました" in w["error"] and "途中から再開する" in w["error"]
    assert w["log"][-1]["kind"] == "error"
    w = store.load("20261104-000004-dddddd")
    assert w["interrupted_session"] == "" and "もう一度押してください" in w["error"]
    assert store.load("20261104-000002-bbbbbb")["status"] == "点検中"
    assert store.load("20261104-000003-cccccc")["status"] == "改定案あり"


def test_resume_endpoint(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    monkeypatch.setattr(store, "WORK", tmp_path)
    started = []
    monkeypatch.setattr(M, "_run_draft", lambda wid, board=False, resume="": started.append((wid, board, resume)))
    _work(tmp_path, "20261104-000005-eeeeee", status="改定案エラー", interrupted_session="sesn_now", draft_with_board=True)
    _work(tmp_path, "20261104-000006-ffffff", status="改定案エラー")  # 再開できる作業がない
    c = TestClient(M.app)
    assert c.post("/works/20261104-000006-ffffff/draft/resume", follow_redirects=False).status_code == 409
    r = c.post("/works/20261104-000005-eeeeee/draft/resume", follow_redirects=False)
    assert r.status_code == 303 and store.load("20261104-000005-eeeeee")["status"] == "改定案作成中"
    import time
    for _ in range(50):
        if started:
            break
        time.sleep(0.02)
    assert started == [("20261104-000005-eeeeee", True, "sesn_now")]
