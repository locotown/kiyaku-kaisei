"""画面のサンプルがすべて読み込めるかのテスト。API は呼ばない（点検の開始は差し替える）。"""

import shutil

import pytest


@pytest.mark.parametrize("key,articles,rules", [("standard", 87, 0), ("collection", 74, 3), ("old", 74, 0), ("docx", 74, 3)])
def test_sample_loads(monkeypatch, key, articles, rules):
    from fastapi.testclient import TestClient

    import app.main as M
    from app import store

    started = []
    monkeypatch.setattr(M, "_run_review", lambda wid: started.append(wid))
    c = TestClient(M.app)
    assert M.SAMPLES[key]["title"] in c.get("/").text
    r = c.post("/works", data={"name": M.SAMPLES[key]["name"], "sample": key}, follow_redirects=False)
    assert r.status_code == 303
    wid = r.headers["location"].rsplit("/", 1)[1]
    try:
        work = store.load(wid)
        assert work["articles"] == articles
        assert sum(1 for d in work["documents"] if d["kind"] == "細則") == rules
        assert M._source(wid).suffix == M.SAMPLES[key]["path"].suffix
        assert started == [wid]
    finally:
        shutil.rmtree(store.path(wid))
