"""審査員向けの公開版のログイン（core/auth.py）。API は呼ばない。"""

import json
import time

import pytest

from core import auth


def accounts_env(until="2099-12-31"):
    return json.dumps([
        {"id": "judge1", "pw": auth.hash_password("pw-one"), "until": until, "admin": False},
        {"id": "judge2", "pw": auth.hash_password("pw-two"), "until": until, "admin": False},
        {"id": "author", "pw": auth.hash_password("pw-admin"), "until": until, "admin": True},
    ])


@pytest.fixture
def pub(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    import app.main as M
    from app import store
    monkeypatch.setenv("KIYAKU_ACCOUNTS", accounts_env())
    monkeypatch.setenv("KIYAKU_SESSION_SECRET", "test-secret")
    monkeypatch.setattr(store, "WORK", tmp_path / "work")
    monkeypatch.setattr(store, "CONSULT", tmp_path / "consult")
    monkeypatch.setattr(M, "_run_review", lambda wid: None)   # AI は動かさない
    auth._fails.clear()

    def client(uid=None, pw=None):
        c = TestClient(M.app)
        if uid:
            r = c.post("/login", data={"id": uid, "password": pw, "next": "/"}, follow_redirects=False)
            assert r.status_code == 303, r.text
        return c
    return M, store, client


def new_work(c):
    r = c.post("/works", data={"name": "テスト", "sample": "standard"}, follow_redirects=False)
    assert r.status_code == 303, r.text
    return r.headers["location"].rsplit("/", 1)[-1]


def test_login_required_and_wrong_password(pub):
    M, store, client = pub
    c = client()
    r = c.get("/", headers={"accept": "text/html"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")
    assert c.get("/healthz").status_code == 200 and c.get("/login").status_code == 200
    r = c.post("/login", data={"id": "judge1", "password": "違う"})
    assert r.status_code == 401 and "ID かパスワードが違います" in r.text
    assert c.post("/works/x/draft").status_code == 401                       # ログインなしの操作は受け付けない


def test_each_account_sees_only_its_own_works(pub):
    M, store, client = pub
    a, b, admin = client("judge1", "pw-one"), client("judge2", "pw-two"), client("author", "pw-admin")
    wa = new_work(a)
    assert store.load(wa)["owner"] == "judge1"
    assert a.get(f"/works/{wa}").status_code == 200
    assert b.get(f"/works/{wa}").status_code == 404                          # ほかの人の作業は開けない
    assert b.post(f"/works/{wa}/draft").status_code == 404
    assert b.get(f"/works/{wa}/taisho").status_code == 404
    assert wa not in b.get("/").text and wa in a.get("/").text
    assert admin.get(f"/works/{wa}").status_code == 200                      # 管理者は見られる
    page = a.get("/").text
    assert "審査用の公開版です" in page and "ログアウト（judge1）" in page


def test_seed_works_are_per_account(pub, monkeypatch):
    M, store, client = pub
    monkeypatch.setattr(store, "SEED", store.ROOT / "data/public/persona_works")   # ほかのテストでは写さない設定なので戻す
    a, b = client("judge1", "pw-one"), client("judge2", "pw-two")
    a.get("/"), b.get("/")
    page = a.get("/").text
    # 公開版では、写しが他人の作業に見えないよう「見本の作業（あなた専用の写し）」と書く（11/8 作者の声）
    assert "見本の作業（架空のサンプルで総会まで済ませたもの。あなた専用の写し）" in page
    assert "あなたが作った作業は、まだありません。" in page and "想定ユーザーの作業（架空・確認用）" not in page
    owners = {json.loads(f.read_text(encoding="utf-8")).get("owner") for f in store.WORK.glob("*/work.json")}
    assert owners <= {"judge1", "judge2"} and len(owners) == 2
    from core import auth as A
    token = A.CURRENT.set(A.accounts()["judge1"])
    try:
        assert A.spent()[0] == 0 and not A.ai_refusal()   # 写したサンプルの費用は上限に数えない
    finally:
        A.CURRENT.reset(token)


def test_expired_account_and_idle_session(pub, monkeypatch):
    M, store, client = pub
    monkeypatch.setenv("KIYAKU_ACCOUNTS", accounts_env(until="2020-01-01"))
    c = client()
    r = c.post("/login", data={"id": "judge1", "password": "pw-one"})
    assert r.status_code == 401 and "期限が過ぎました" in r.text
    monkeypatch.setenv("KIYAKU_ACCOUNTS", accounts_env())
    old = auth.make_cookie("judge1")
    monkeypatch.setattr(auth.time, "time", lambda: time.time_ns() / 1e9 + auth.IDLE + 10)
    assert auth.from_cookie(old) is None                                      # 12時間操作がなければ切れる


def test_forged_cookie_rejected(pub):
    M, store, client = pub
    good = auth.make_cookie("judge1")
    body, sig = good.rsplit(".", 1)
    import base64
    forged = base64.urlsafe_b64encode(json.dumps({"u": "author", "t": int(time.time())}).encode()).decode().rstrip("=")
    assert auth.from_cookie(forged + "." + sig) is None and auth.from_cookie(good)["id"] == "judge1"


def test_rate_limit(pub):
    M, store, client = pub
    c = client()
    for _ in range(auth.FAIL_MAX):
        c.post("/login", data={"id": "judge2", "password": "x"})
    r = c.post("/login", data={"id": "judge2", "password": "pw-two"})
    assert r.status_code == 401 and "しばらく受け付けません" in r.text


def test_ai_cost_limit(pub, monkeypatch):
    M, store, client = pub
    a = client("judge1", "pw-one")
    wa = new_work(a)
    store.mutate(wa, lambda d: d.setdefault("costs", []).append({"step": "点検", "cost": {"amount": 2500, "currency": "USD"}}))
    monkeypatch.setenv("KIYAKU_LIMIT_USER_USD", "20")
    r = a.post("/works", data={"name": "二つ目", "sample": "standard"}, follow_redirects=False)
    assert r.status_code == 429                                               # 上限を超えたら新しい AI の処理を始めない
    assert a.get(f"/works/{wa}").status_code == 200                           # これまでの作業は見られる
    admin = client("author", "pw-admin")
    assert admin.post("/works", data={"name": "管理者", "sample": "standard"}, follow_redirects=False).status_code == 303


def test_local_use_has_no_login(monkeypatch):
    from fastapi.testclient import TestClient

    import app.main as M
    monkeypatch.delenv("KIYAKU_ACCOUNTS", raising=False)
    assert TestClient(M.app).get("/", follow_redirects=False).status_code == 200


# ---- 11/8 セキュリティの点検から ------------------------------------------------------

def test_lockout_by_others_does_not_block_judge(pub):
    """他の接続元が審査員の ID で失敗を重ねても、審査員本人はログインできる（ID だけで止めない）。"""
    M, store, client = pub
    c = client()
    for _ in range(auth.FAIL_MAX + 2):
        c.post("/login", data={"id": "judge2", "password": "x"}, headers={"x-forwarded-for": "203.0.113.9"})
    r = c.post("/login", data={"id": "judge2", "password": "pw-two"}, headers={"x-forwarded-for": "198.51.100.7"},
               follow_redirects=False)
    assert r.status_code == 303
    # 接続元は、公開先のプロキシが最後に付け足した値で数える（先頭は偽れる）
    for i in range(auth.FAIL_MAX):
        c.post("/login", data={"id": "judge1", "password": "x"}, headers={"x-forwarded-for": f"10.0.0.{i}, 192.0.2.1"})
    r = c.post("/login", data={"id": "judge1", "password": "pw-one"}, headers={"x-forwarded-for": "10.9.9.9, 192.0.2.1"})
    assert r.status_code == 401 and "しばらく受け付けません" in r.text


def test_broken_accounts_env_keeps_login_required(pub, monkeypatch):
    """KIYAKU_ACCOUNTS が壊れていても、ログインなしで開ける状態にしない。"""
    M, store, client = pub
    monkeypatch.setenv("KIYAKU_ACCOUNTS", "[{oops")
    r = client().get("/", follow_redirects=False)
    assert r.status_code in (303, 401) and "ログイン" in (r.text + r.headers.get("location", ""))


def test_ai_run_on_seeded_copy_and_photos_are_counted(pub, monkeypatch):
    """写したサンプルで動かした AI の費用と、写真の読み取りの費用も、上限に数える。"""
    M, store, client = pub
    a = client("judge1", "pw-one")
    wid = new_work(a)
    store.mutate(wid, lambda d: d.update(seeded=True, seed_costs=1, status="点検済み",
                                         costs=[{"cost": {"amount": 9999}}, {"cost": {"amount": 300}}],
                                         notes=[{"id": "1", "status": "読み取り済み", "cost_usd": 0.5}]))
    token = auth.CURRENT.set(auth.accounts()["judge1"])
    try:
        assert round(auth.spent()[0], 2) == 3.5          # 元の $99.99 は数えず、写したあとの $3 と写真の $0.5
    finally:
        auth.CURRENT.reset(token)


def test_parallel_ai_runs_are_limited(pub):
    """費用は終わってから記録されるので、同時に動かせる処理の数を限る。"""
    M, store, client = pub
    a = client("judge1", "pw-one")
    for _ in range(auth.MAX_RUNNING):
        new_work(a)                                      # AI は止めてあるので「点検中」のまま
    r = a.post("/works", data={"name": "三つ目", "sample": "standard"}, follow_redirects=False)
    assert r.status_code == 429


def test_consult_cannot_use_others_work(pub, monkeypatch):
    """相談で、他人の作業の規約を使えない。"""
    M, store, client = pub
    import app.consult_app as C
    monkeypatch.setattr(C, "_run", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(C.threading, "Thread", lambda *a, **k: type("T", (), {"start": lambda self: None})())
    wid = new_work(client("judge1", "pw-one"))
    b = client("judge2", "pw-two")
    r = b.post("/consult", data={"mode": "ask", "question": "総会の定足数は？", "work_id": wid}, follow_redirects=False)
    assert r.status_code == 303
    saved = [json.loads(f.read_text(encoding="utf-8")) for f in store.CONSULT.glob("*.json") if not f.name.startswith("profile")]
    assert saved and all(s["work_id"] == "" and s["work_name"] == "" for s in saved)


def test_taisho_labels_are_escaped(monkeypatch):
    from core import taisho
    lab = "〔<script>案〕"
    monkeypatch.setattr(taisho, "para_pairs", lambda o, n: [{"kind": "same", "new_label": lab, "new": "x", "old": "x", "old_label": lab}])
    a = type("A", (), {"kind": "改正"})()
    out = taisho._pairs_html({"amendment": a, "old_text": "１　x\n２　y", "new_text": "１　x\n２　y"})
    assert "<script>" not in out and "&lt;script&gt;" in out


def test_huge_image_and_docx_bomb_are_refused(tmp_path):
    import io
    import zipfile

    from PIL import Image

    from core import ingest, notes
    buf = io.BytesIO()
    Image.new("1", (9000, 9000)).save(buf, "PNG")       # 小さなファイルでも、展開すると大きい画像
    with pytest.raises(ValueError):
        notes.preprocess(buf.getvalue())
    p = tmp_path / "bomb.docx"
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", b"0" * (ingest.MAX_DOCX_UNZIPPED + 1))
    with pytest.raises(ingest.UnsupportedFormat):
        ingest._read_docx(p)
