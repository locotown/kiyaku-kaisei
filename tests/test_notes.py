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


def test_memo_and_manual_additions(work, monkeypatch):
    """提案ごとの補足と、写真にない内容を手で足した分（会議のあとで見返して直す・足す）。"""
    reading = N.PhotoReading(document="理事会の検討資料", ident="", page="", note="", annotations=[
        ann(target="検討資料の議題", item=2, kind="判断", handwriting="☑採用", decision="採用"),
    ])
    monkeypatch.setattr(N, "read_photo", lambda jpeg, context, effort="high": (reading, {}))
    batch = upload(work, "board")
    b = read_until_done(batch)
    page = work.get(f"/works/{WID}/notes/{batch}").text
    assert "写真にない内容を足す" in page and "議題1 総会" in page
    pid = b["proposals"][0]["id"]
    form = {f"act_{pid}": "反映する", f"text_{pid}": "採用", f"memo_{pid}": "管理会社の説明を聞いて決めた",
            "add_place": "item:0", "add_decision": "見送り", "add_text": "次回もう一度話す", "add_memo": "会議の最後に出た話"}
    work.post(f"/works/{WID}/notes/{batch}/apply", data=form)
    w = store.load(WID)
    assert w["board_decisions"]["1"]["decision"] == "採用"
    assert "管理会社の説明を聞いて決めた" in w["board_decisions"]["1"]["note"]       # 補足は議題のメモに残る
    assert w["board_decisions"]["0"]["decision"] == ""                                 # ①に「見送り」は選べない → 記録しない
    assert "☑見送り／次回もう一度話す" in w["board_decisions"]["0"]["note"]            # メモとして残す
    assert "会議の最後に出た話" in w["board_decisions"]["0"]["note"]
    bb = M._note_batch(w, batch)
    assert bb["proposals"][0]["memo"] == "管理会社の説明を聞いて決めた"
    manual = [p for p in bb["proposals"] if p.get("manual")]
    assert [p["status"] for p in manual] == ["反映済み"]
    assert "手で足した内容" in work.get(f"/works/{WID}/notes/{batch}").text
    # 新旧対照表の書き込みに、行を選んで宿題を足す
    reading2 = N.PhotoReading(document="新旧対照表", ident="", page="", note="", annotations=[])
    monkeypatch.setattr(N, "read_photo", lambda jpeg, context, effort="high": (reading2, {}))
    batch2 = upload(work, "taisho")
    read_until_done(batch2)
    work.post(f"/works/{WID}/notes/{batch2}/apply", data={"add_place": "row:2", "add_text": "理事長に確認", "add_memo": "委員会のあとで"})
    t = store.load(WID)["todos"][-1]
    assert t["text"] == "理事長に確認" and t["where"].startswith("行2 第20条") and t["memo"] == "委員会のあとで"


def test_edit_articles_directly_and_revert(work):
    """改定案の条の文を、写真を通さずに直す。開いたあとに改定案が変わっていたら上書きしない。AI の文に戻せる。"""
    page = work.get(f"/works/{WID}/articles").text
    assert "条の文を直す" in page and "行2" in page
    ident = M._ident(WID, store.load(WID))
    key = "規約|第20条"
    r = work.post(f"/works/{WID}/articles", data={"ident": ident, f"text_{key}": "第20条　委員会で見返して直した文。",
                                                  f"note_{key}": "11/4 の委員会の議論を踏まえて"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].endswith("saved=1")
    w = store.load(WID)
    am = next(a for a in w["draft"]["amendments"] if a["article"] == "第20条")
    assert am["text"] == "第20条　委員会で見返して直した文。"
    assert w["human_edits"][key] == {**w["human_edits"][key], "original": "第20条　…", "note": "11/4 の委員会の議論を踏まえて"}
    assert "委員会で見返して直した文" in (store.path(WID) / "taisho.html").read_text(encoding="utf-8")
    # 古い版の画面からの保存は断る（ほかの人が直した文を黙って上書きしない）
    assert work.post(f"/works/{WID}/articles", data={"ident": ident, f"text_{key}": "古い画面から"}).status_code == 409
    # AI が作った文に戻す
    ident2 = M._ident(WID, store.load(WID))
    work.post(f"/works/{WID}/articles", data={"ident": ident2, f"revert_{key}": "1"})
    w = store.load(WID)
    assert next(a for a in w["draft"]["amendments"] if a["article"] == "第20条")["text"] == "第20条　…"
    assert key not in w["human_edits"]


def test_todos_edit_done_delete_add(work):
    store.update(WID, todos=[{"text": "古い宿題", "where": "行1", "at": "11月04日"},           # id のない古い形
                             {"id": "abc", "text": "消す宿題", "where": "全体", "at": "11月04日"}])
    assert "宿題・メモを保存する" in work.get(f"/works/{WID}").text
    r = work.post(f"/works/{WID}/todos", data={"back": "board", "text_i0": "直した宿題", "memo_i0": "経緯", "done_i0": "1",
                                               "text_abc": "消す宿題", "del_abc": "1", "new_text": "足した宿題", "new_where": "第25条"},
                  follow_redirects=False)
    assert r.headers["location"].endswith("#board")
    todos = store.load(WID)["todos"]
    assert [(t["text"], t.get("memo"), t.get("done"), t["where"]) for t in todos] == [
        ("直した宿題", "経緯", True, "行1"), ("足した宿題", "", False, "第25条")]


def test_bulk_pick_and_empty_unreadable_stays(work, monkeypatch):
    """まとめて「反映する」を選べる。中身のない「読めない」提案は、反映を選んでも反映済みにせず残す（人の確認 第1回）。"""
    reading = N.PhotoReading(document="理事会の検討資料", ident="", page="", note="", annotations=[
        ann(target="検討資料の議題", item=2, kind="判断", handwriting="☑採用", decision="採用"),
        ann(kind="読めない", handwriting="？？"),
    ])
    monkeypatch.setattr(N, "read_photo", lambda jpeg, context, effort="high": (reading, {}))
    batch = upload(work, "board")
    b = read_until_done(batch)
    assert "すべて「反映する」にする" in work.get(f"/works/{WID}/notes/{batch}").text
    form = {f"act_{p['id']}": "反映する" for p in b["proposals"]} | {f"text_{p['id']}": p.get("proposed") or "" for p in b["proposals"]}
    work.post(f"/works/{WID}/notes/{batch}/apply", data=form)
    left = {p["kind"]: p["status"] for p in M._note_batch(store.load(WID), batch)["proposals"]}
    assert left == {"判断": "反映済み", "読めない": "未確認"}


def test_human_edit_marks_and_ai_review(work, monkeypatch):
    """人が直した条には、資料に「AI の確認前」の印が出る。AI に確かめてもらうと「AI 確認済み」に変わり、
    そのあと文を直すと、また「確認前」に戻る（人の確認 第1回：素人の手直しで悪くならないように）。"""
    import io as _io

    from docx import Document

    from core import editcheck as E

    key = "規約|第20条"
    ident = M._ident(WID, store.load(WID))
    work.post(f"/works/{WID}/articles", data={"ident": ident, f"text_{key}": "第20条　区分所有者は、委員会で直した文とする。"})
    taisho = (store.path(WID) / "taisho.html").read_text(encoding="utf-8")
    assert "委員会で直した文（AI の確認前）" in taisho
    doc = Document(_io.BytesIO(work.get(f"/works/{WID}/taisho.docx").content))
    assert "委員会で直した文（AI の確認前）" in "\n".join(c.text for row in doc.tables[0].rows for c in row.cells)
    assert "AI の確認前" in work.get(f"/works/{WID}").text                     # ステップ3にも案内
    assert M.edit_counts(store.load(WID))["unchecked"] == ["第20条"]

    seen = {}

    def fake(material, effort="medium"):
        seen["material"] = material
        return E.EditReview(verdict="気になる点あり", summary="主語が変わっています。", concerns=[
            E.EditConcern(kind="意味が変わった・あいまい", point="主語が変わった", basis="AI の元の文の「区分所有者は」", suggestion="元に戻す"),
        ]), {"input_tokens": 10000, "output_tokens": 1000}
    monkeypatch.setattr(E, "review_edit", fake)
    assert work.post(f"/works/{WID}/articles/review", data={"key": key}, follow_redirects=False).status_code == 303
    for _ in range(100):
        r = (store.load(WID)["human_edits"][key].get("review") or {})
        if r.get("status") != "確認中":
            break
        time.sleep(0.05)
    assert r["status"] == "済み" and r["verdict"] == "気になる点あり"
    assert "委員会で直した文" in seen["material"] and "AI が作った改定案の文" in seen["material"]
    assert r["cost_usd"] == pytest.approx(0.06)                                  # 10000×$4 ＋ 1000×$20
    assert store.load(WID)["costs"][-1]["step"].startswith("直した文の確認")
    taisho = (store.path(WID) / "taisho.html").read_text(encoding="utf-8")
    assert "AI 確認済み：気になる点あり" in taisho and "AI の確認前" not in taisho
    page = work.get(f"/works/{WID}/articles").text
    assert "主語が変わった" in page and "AI の確認：気になる点あり" in page
    assert M.edit_counts(store.load(WID))["unchecked"] == []
    assert M.edit_counts(store.load(WID))["flagged"] == ["第20条（気になる点あり）"]   # 「すべて確かめた」だけで終わらせない
    assert "AI が気になる点を挙げた条" in work.get(f"/works/{WID}").text
    # 確かめたあとに文を直すと、また「確認前」に戻る
    ident = M._ident(WID, store.load(WID))
    work.post(f"/works/{WID}/articles", data={"ident": ident, f"text_{key}": "第20条　区分所有者は、もう一度直した文とする。"})
    assert "委員会で直した文（AI の確認前）" in (store.path(WID) / "taisho.html").read_text(encoding="utf-8")


def test_review_drops_concerns_without_basis(monkeypatch):
    from core import editcheck as E

    class Msg:
        stop_reason = "end_turn"
        usage = None
        parsed_output = E.EditReview(verdict="気になる点あり", summary="", concerns=[
            E.EditConcern(kind="要確認", point="根拠のない指摘", basis=" ", suggestion="")])

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get_final_message(self):
            return Msg()

    class Client:
        class beta:
            class messages:
                @staticmethod
                def stream(**kw):
                    return Stream()

    monkeypatch.setattr(E, "client", lambda: Client())
    review, _ = E.review_edit("材料")
    assert review.concerns == [] and review.verdict == "問題なし"           # 根拠を示せない指摘は出さない


def test_review_progress_is_visible(work):
    """AI が確かめている間、何を確かめていて何秒たったか・順番待ちが画面に出る（人の確認 第3回：動いているか分からない）。"""
    from datetime import datetime, timedelta

    started = (datetime.now() - timedelta(seconds=12)).isoformat(timespec="seconds")
    store.update(WID, human_edits={
        "規約|第20条": {"text": "第20条　直した", "original": "第20条　…", "at": "", "note": "",
                      "review": {"status": "確認中", "queued": False, "started": started, "for_text": "第20条　直した"}},
        "規約|第47条": {"text": "第47条　直した", "original": "第47条　…", "at": "", "note": "",
                      "review": {"status": "確認中", "queued": True, "for_text": "第47条　直した"}},
    })
    page = work.get(f"/works/{WID}/articles").text
    assert "AI が第20条を確かめています" in page and "秒たちました" in page
    assert "ほかに 1条が順番を待っています" in page and "順番を待っています（前の条が終わると始まります）" in page
    p = M._review_progress(store.load(WID)["human_edits"])
    assert p["active"] == "第20条" and p["left"] == 2 and 10 <= p["elapsed"] <= 60
