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
    _work(tmp_path, "20261104-000001-aaaaaa", status="改定案作成中",
          log=[{"t": "10:00:00", "kind": "session", "text": "sesn_abc"}, {"t": "10:01:00", "kind": "tool", "text": "条文を読む"}])
    _work(tmp_path, "20261104-000002-bbbbbb", status="点検中", demo_busy=True)  # デモの録画用は切り替えない
    _work(tmp_path, "20261104-000003-cccccc", status="改定案あり")             # 処理中でないものは触らない

    assert M.recover_interrupted() == ["20261104-000001-aaaaaa"]
    w = store.load("20261104-000001-aaaaaa")
    assert w["status"] == "改定案エラー" and w["interrupted"] == "改定案作成中" and w["interrupted_session"] == "sesn_abc"
    assert "途中で止まりました" in w["error"] and "もう一度押してください" in w["error"]
    assert w["log"][-1]["kind"] == "error"
    assert store.load("20261104-000002-bbbbbb")["status"] == "点検中"
    assert store.load("20261104-000003-cccccc")["status"] == "改定案あり"
