"""書き込みの反映（写真 → 読み取り → 提案 → 人が確かめて反映）。AI の読み取りは偽物に置き換える（費用はかからない）。"""

import io
import shutil
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import main as M
from app import store
from core import notes as N
from core.board import fix_tiers
from tests.test_board import FINDING, make_draft, make_paper

WID = "20261104-000030-ntest1"


def png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(buf, "PNG")
    return buf.getvalue()


def ann(**kw):
    base = {"target": "不明", "row": None, "item": None, "kind": "メモ・宿題", "handwriting": "", "new_text": "", "decision": "",
            "choice_point": None, "choice_option": "", "confidence": "高", "reason": "赤ペン"}
    return N.Annotation(**{**base, **kw})


@pytest.fixture
def work(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "WORK", tmp_path)
    draft, paper = make_draft(), make_paper()
    fix_tiers(paper, draft)  # 議題：1 総会（①）、2 責務（②）、3 駐車場（②）、4 参照の整理（③）
    d = tmp_path / WID
    d.mkdir()
    shutil.copy(M.SAMPLE, d / "source.txt")
    store.save(WID, {"name": "t", "info": {"型": "単棟型"}, "status": "検討資料あり", "articles": 87, "log": [],
                     "findings": [FINDING], "decisions": {"0": {"decision": "採用", "reason": ""}},
                     "draft": draft.to_dict(), "board": paper.model_dump(), "board_decisions": {}})
    return TestClient(M.app)


def read_until_done(batch):
    for _ in range(100):
        b = M._note_batch(store.load(WID), batch)
        if b["status"] != "読み取り中":
            return b
        time.sleep(0.05)
    raise AssertionError("読み取りが終わりません")


def upload(c, doc):
    r = c.post(f"/works/{WID}/notes", data={"doc": doc}, files=[("photos", ("a.png", png(), "image/png"))], follow_redirects=False)
    assert r.status_code == 303
    return r.headers["location"].rsplit("/", 1)[1]


def test_board_photo_to_decisions(work, monkeypatch):
    reading = N.PhotoReading(document="理事会の検討資料", ident="", page="2 / 5", note="", annotations=[
        ann(target="検討資料の議題", item=2, kind="判断", handwriting="☑採用", decision="採用"),
        ann(target="検討資料の議題", item=2, kind="メモ・宿題", handwriting="管理会社に確認"),
        ann(target="検討資料の議題", item=1, kind="判断", handwriting="☑見送り", decision="見送り"),  # ①に見送りはない → メモにする
        ann(kind="読めない", handwriting="？？"),
    ])
    monkeypatch.setattr(N, "read_photo", lambda jpeg, context, effort="high": (reading, {"input_tokens": 3000, "output_tokens": 500}))
    batch = upload(work, "board")
    b = read_until_done(batch)
    kinds = [(p["kind"], p.get("proposed")) for p in b["proposals"]]
    assert ("判断", "採用") in kinds and ("理事会のメモ", "管理会社に確認") in kinds
    assert ("理事会のメモ", "☑見送り") in kinds          # 選べない判断は、勝手に記録せずメモの提案にする
    assert b["cost_usd"] == pytest.approx(0.022)          # 3000×$4 ＋ 500×$20（100万トークンあたり）
    assert "反映する" in work.get(f"/works/{WID}/notes/{batch}").text
    form = {f"act_{p['id']}": "反映する" for p in b["proposals"] if p["kind"] != "読めない"}
    form.update({f"text_{p['id']}": p["proposed"] for p in b["proposals"] if p["kind"] != "読めない"})
    assert work.post(f"/works/{WID}/notes/{batch}/apply", data=form, follow_redirects=False).status_code == 303
    w = store.load(WID)
    assert w["board_decisions"]["1"]["decision"] == "採用" and w["board_decisions"]["1"]["history"]  # 画面と同じ保存・履歴
    assert "管理会社に確認" in w["board_decisions"]["1"]["note"]
    left = [p for p in M._note_batch(w, batch)["proposals"] if p["status"] == "未確認"]
    assert [p["kind"] for p in left] == ["読めない"]       # 選ばなかった提案は残る


def test_taisho_photo_edits_text_and_survives_redraft(work, monkeypatch):
    new = "第20条　区分所有者は、委員会で直した文とする。"
    reading = N.PhotoReading(document="新旧対照表", ident="ID ntest1-000000", page="1 / 3", note="", annotations=[
        ann(target="新旧対照表の行", row=2, kind="文言の修正", handwriting="「…」→「委員会で直した文」", new_text=new),
        ann(target="新旧対照表の行", row=1, kind="メモ・宿題", handwriting="？ 管理会社に確認"),
    ])
    monkeypatch.setattr(N, "read_photo", lambda jpeg, context, effort="high": (reading, {}))
    batch = upload(work, "taisho")
    b = read_until_done(batch)
    edit = next(p for p in b["proposals"] if p["kind"] == "文言の修正")
    assert edit["article"] == "第20条" and edit["current"] == "第20条　…" and edit["proposed"] == new
    form = {f"act_{p['id']}": "反映する" for p in b["proposals"]} | {f"text_{p['id']}": p["proposed"] for p in b["proposals"]}
    work.post(f"/works/{WID}/notes/{batch}/apply", data=form)
    w = store.load(WID)
    assert next(a for a in w["draft"]["amendments"] if a["article"] == "第20条")["text"] == new
    assert w["human_edits"]["規約|第20条"]["original"] == "第20条　…"   # AI の元の文も残す
    assert w["todos"][0]["text"] == "？ 管理会社に確認"
    assert "新旧対照表" in (store.path(WID) / "taisho.html").read_text(encoding="utf-8")
    redraft = make_draft()                                                # 改定案を作り直しても
    assert M._keep_human_edits(w, redraft) == ["第20条"]                   # 委員会で直した文を引き継ぐ
    assert next(a for a in redraft.amendments if a.article == "第20条").text == new


def test_upload_rejects_non_images(work):
    r = work.post(f"/works/{WID}/notes", data={"doc": "board"}, files=[("photos", ("a.txt", b"not an image", "text/plain"))],
                  headers={"accept": "text/html"})
    assert r.status_code == 400 and "写真を読み込めませんでした" in r.text


def test_interrupted_reading_can_resume(work, monkeypatch):
    store.mutate(WID, lambda d: d.setdefault("notes", []).append(
        {"id": "20261104000000", "at": "11月04日", "doc": "board", "status": "読み取り中", "photos": [], "proposals": [],
         "ident": "", "cost_usd": 0.0, "skipped": 0}))
    M.recover_interrupted()
    assert M._note_batch(store.load(WID), "20261104000000")["status"] == "中断"
