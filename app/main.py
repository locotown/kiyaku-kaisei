"""画面（FastAPI）。

起動:  uv run uvicorn app.main:app --reload
流れ:  規約のアップロード → 点検（進み具合を表示）→ 指摘の採用・不採用 → 改定案と新旧対照表
"""

from __future__ import annotations

import shutil
import threading
import traceback
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import store
from core.config import ROOT
from core.findings import Finding
from core.ingest import SUPPORTED, UnsupportedFormat, load_kiyaku
from core.taisho import to_html, to_markdown

app = FastAPI(title="ととのう規約")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")  # デザイントークンなど
SAMPLE = ROOT / "evals/data/r7_tantou_before.txt"
# 画面で選べるサンプル（すべて公開資料か架空のデータ）
SAMPLES = {
    "standard": {"path": SAMPLE, "name": "サンプル：改正前の標準管理規約（単棟型）",
                 "title": "改正前の標準管理規約", "format": "テキスト",
                 "contents": "規約本体 87条（細則なし）",
                 "point": "国の標準どおりの規約。改正で必ず直す箇所（必須）が、標準の条番号どおりに見つかるかを確認できます。"},
    "collection": {"path": ROOT / "evals/data/old_collection.txt", "name": "サンプル：細則を含む規約集（架空）",
                   "title": "細則を含む規約集", "format": "テキスト",
                   "contents": "規約 74条＋細則3種（総会運営・駐車場使用・ペット飼育）＋改正履歴・メモ",
                   "point": "規約と細則を分けて読み込み、細則への指摘（普通決議）や、規約と細則の食い違いを確認できます。"},
    "old": {"path": ROOT / "evals/data/old_style_kiyaku.txt", "name": "サンプル：長く改正していない古い規約（架空）",
            "title": "長く改正していない古い規約", "format": "テキスト",
            "contents": "規約本体 74条（細則なし。条番号が標準と違う）",
            "point": "条番号が標準管理規約と違っていても、見出しと内容から該当する条を探せるかを確認できます。"},
    "docx": {"path": ROOT / "evals/data/old_collection.docx", "name": "サンプル：Word の規約集（架空）",
             "title": "Word（.docx）の規約集", "format": "Word",
             "contents": "「細則を含む規約集」と同じ内容。改正履歴は表",
             "point": "Word で管理している規約集を、そのまま読み込めるかを確認できます。"},
}
DECISIONS = ("採用", "不採用", "保留")
CHOICE_HELP = {"採用": "改定案に入れる", "保留": "まだ決めない（改定案には入れない）", "不採用": "今回は改定しない"}
BUSY = ("点検中", "改定案作成中", "検討資料作成中", "説明文作成中")


def _source(work_id: str) -> Path:
    files = [p for p in store.path(work_id).glob("source.*")]
    if not files:
        raise HTTPException(404, "規約のファイルがありません")
    return files[0]


def _corpus(work_id: str):
    """規約本体と細則を読み込む（規約集でなければ規約本体だけ）。"""
    from core.corpus import Corpus
    from core.ingest import load_collection

    corpus = Corpus.from_collection(load_collection(_source(work_id)))
    if len(corpus.main.articles) < 3:
        corpus = Corpus(load_kiyaku(_source(work_id)))
    return corpus


def _findings(work: dict) -> list[Finding]:
    return [Finding(**f) for f in work.get("findings", [])]


def _run_review(work_id: str) -> None:
    from core.review import run_review

    work = store.load(work_id)
    try:
        corpus = _corpus(work_id)
        result = run_review(corpus.main, work["info"], rules=corpus.rules, on_event=lambda k, t: store.append_log(work_id, k, t),
                            title=f"点検：{work['name']}")
        decisions = {str(i): {"decision": "採用" if f.category == "必須" else "保留", "reason": ""}
                     for i, f in enumerate(result.findings)}
        store.update(work_id, status="点検済み", findings=[f.to_dict() for f in result.findings],
                     decisions=decisions, summary=result.summary, review_session=result.session_id,
                     review_cost=result.usage.get("list_cost"),
                     costs=work.get("costs", []) + [_cost_entry("点検", result.usage.get("list_cost"))])
    except Exception as e:
        store.append_log(work_id, "error", f"{type(e).__name__}: {e}")
        store.update(work_id, status="エラー", error=traceback.format_exc(limit=3))


def _board(work: dict):
    from core.board import BoardPaper

    return BoardPaper.model_validate(work["board"]) if work.get("board") else None


def _draft(work: dict):
    from core.draft import Amendment, Draft

    d = work.get("draft")
    return Draft(amendments=[Amendment(**a) for a in d["amendments"]], notes=d.get("notes", "")) if d else None


def _points(work: dict) -> dict:
    """理事会の議題ごとの、組合が選ぶ点（〔選択〕）。"""
    from core.board import choice_points

    paper = _board(work)
    return choice_points(paper, _draft(work)) if paper else {}


def _org(work: dict) -> str:
    """マンション名・管理組合名（住民向けの説明・検討資料・新旧対照表に入れる）。作業の名前は出さない。"""
    return str(work.get("org", "")).strip()


def _write_taisho(work_id: str, work: dict, draft, corpus) -> None:
    title = f"{_org(work)} 管理規約 新旧対照表（案）".strip()
    d = store.path(work_id)
    (d / "taisho.html").write_text(to_html(draft, corpus, title), encoding="utf-8")
    (d / "taisho.md").write_text(to_markdown(draft, corpus, title), encoding="utf-8")


def _rerender(work_id: str) -> None:
    """マンション名を変えたら、作ってある資料（新旧対照表・検討資料・住民向け説明）を AI を使わずに書き直す。"""
    from core.board import apply_to_draft, to_html as board_html
    from core.explain import Explanation, to_html as explain_html

    work = store.load(work_id)
    draft, paper = _draft(work), _board(work)
    d = store.path(work_id)
    if draft and (d / "taisho.html").exists():
        _write_taisho(work_id, work, draft, _corpus(work_id))
    if paper and (d / "board.html").exists():
        (d / "board.html").write_text(board_html(paper, work.get("board_decisions") or None, _org(work), _points(work)),
                                      encoding="utf-8")
    if work.get("explain") and draft and (d / "explain.html").exists():
        shown = apply_to_draft(draft, paper, work.get("board_decisions", {})) if paper else draft
        (d / "explain.html").write_text(explain_html(Explanation.model_validate(work["explain"]), _org(work), shown),
                                        encoding="utf-8")


def _run_draft(work_id: str, with_board: bool = False) -> None:
    from core.board import decisions_text
    from core.drafting import run_draft
    from core.progress import draft_plan

    work = store.load(work_id)
    try:
        corpus = _corpus(work_id)
        adopted = [f for i, f in enumerate(_findings(work)) if work["decisions"][str(i)]["decision"] == "採用"]
        board = decisions_text(_board(work), work.get("board_decisions", {})) if with_board and work.get("board") else ""
        result = run_draft(corpus.main, adopted, work["info"], rules=corpus.rules, on_event=lambda k, t: store.append_log(work_id, k, t),
                           title=f"改定案：{work['name']}", board=board)
        d = store.path(work_id)
        if result.draft:
            _write_taisho(work_id, work, result.draft, corpus)
        extra = {"draft_reflects_board": bool(board), "draft_stale": False} if result.draft else {}
        if result.draft and not board:
            extra.update(board=None, board_decisions={})  # 改定案を作り直したら、理事会の検討資料も作り直す
        step = "改定案の作り直し" if work.get("draft") else "改定案"
        store.update(work_id, status="改定案あり" if result.draft else "改定案エラー",
                     draft=result.draft.to_dict() if result.draft else None, **extra,
                     draft_errors=result.errors, draft_evaluations=result.evaluations,
                     draft_session=result.session_id, draft_cost=result.usage.get("list_cost"),
                     draft_stop=result.stop, draft_elapsed=round(result.elapsed_sec),
                     draft_precedent=result.precedent, draft_checks=result.checks,
                     draft_plan=draft_plan(len(adopted)),
                     costs=store.load(work_id).get("costs", []) + [_cost_entry(step, result.usage.get("list_cost"))])
    except Exception as e:
        store.append_log(work_id, "error", f"{type(e).__name__}: {e}")
        store.update(work_id, status="改定案エラー", error=traceback.format_exc(limit=3))


def _run_explain(work_id: str) -> None:
    from core.draft import Amendment, Draft
    from core.explain import generate, to_html as explain_html
    from core.readability import measure_explanation

    work = store.load(work_id)
    try:
        store.append_log(work_id, "session", "住民向けの説明文を作っています")
        from core.board import apply_to_draft, decisions_text

        draft = Draft(amendments=[Amendment(**a) for a in work["draft"]["amendments"]], notes=work["draft"]["notes"])
        paper, decisions = _board(work), work.get("board_decisions", {})
        draft = apply_to_draft(draft, paper, decisions)  # 理事会が見送りにした改定は説明しない
        ex, _ = generate(draft, work["info"], board=decisions_text(paper, decisions))
        (store.path(work_id) / "explain.html").write_text(explain_html(ex, _org(work), draft), encoding="utf-8")
        store.update(work_id, status="説明文あり", explain=ex.model_dump(), explain_metrics=measure_explanation(ex))
    except Exception as e:
        store.append_log(work_id, "error", f"{type(e).__name__}: {e}")
        store.update(work_id, status="説明文エラー", error=traceback.format_exc(limit=3))


def _run_board(work_id: str) -> None:
    from core.board import default_decisions, generate as board_generate, to_html as board_html
    from core.draft import Amendment, Draft

    work = store.load(work_id)
    try:
        store.append_log(work_id, "session", "理事会の検討資料を作っています")
        draft = Draft(amendments=[Amendment(**a) for a in work["draft"]["amendments"]], notes=work["draft"]["notes"])
        paper, _ = board_generate(draft, work["info"])
        from core.board import choice_points

        (store.path(work_id) / "board.html").write_text(
            board_html(paper, None, _org(work), choice_points(paper, draft)), encoding="utf-8")
        store.update(work_id, status="検討資料あり", board=paper.model_dump(), board_decisions=default_decisions(paper),
                     draft_reflects_board=False)
    except Exception as e:
        store.append_log(work_id, "error", f"{type(e).__name__}: {e}")
        store.update(work_id, status="検討資料エラー", error=traceback.format_exc(limit=3))


def board_state(work: dict) -> dict:
    """理事会の検討の状態。住民向け説明を作れるかを返す。"""
    from core.board import apply_to_draft, remaining_choices, status

    paper = _board(work)
    if not paper:
        return {"ready": False, "needs_redraft": False, "reason": "理事会の検討資料をまだ作っていません。"}
    decisions = work.get("board_decisions", {})
    st = status(paper, decisions, _points(work))
    if not st["done"]:
        reason = f"まだ判断していない議題が{len(st['undecided'])}つあります。"
        if st["needs_choice"]:
            reason += f"〔選択〕のある議題（{'、'.join(st['needs_choice'])}）は、案を選んでください。"
        return {**st, "ready": False, "needs_redraft": False, "reason": reason}
    if st["redraft"] and not work.get("draft_reflects_board"):
        return {**st, "ready": False, "needs_redraft": True,
                "reason": "「修正して採用」「要修正」や、案を選んだ議題があります。理事会の判断を反映して改定案を作り直してください。"}
    draft = _draft(work)
    left = remaining_choices(apply_to_draft(draft, paper, decisions)) if draft else []
    if left:
        return {**st, "ready": False, "needs_redraft": True,
                "reason": f"改定案に〔選択〕が残っています（{'、'.join(left)}）。理事会で選んだ案で改定案を作り直してください。"}
    return {**st, "ready": True, "needs_redraft": False, "reason": ""}



STEP_OF_BUSY = {"点検中": "review", "改定案作成中": "draft", "検討資料作成中": "board", "説明文作成中": "explain"}
STEP_OF_ERROR = {"エラー": "review", "改定案エラー": "draft", "検討資料エラー": "board", "説明文エラー": "explain"}


def journey(work: dict, bstate: dict | None) -> dict:
    """ページ上部の進め方の案内（済んだ段階・いまの段階・次にすること）。"""
    steps = [{"key": "review", "label": "点検", "anchor": "findings"},
             {"key": "decide", "label": "指摘の判断", "anchor": "findings"},
             {"key": "draft", "label": "改定案", "anchor": "next"},
             {"key": "board", "label": "理事会での検討", "anchor": "board"},
             {"key": "explain", "label": "住民向けの説明", "anchor": "explain"},
             {"key": "meeting", "label": "総会後の最新規約", "anchor": "meeting"}]
    draft_ok = bool(work.get("draft")) and not work.get("draft_stale")
    done = {"review": bool(work.get("findings")), "decide": bool(work.get("draft")), "draft": draft_ok,
            "board": draft_ok and bool(bstate and bstate.get("ready")), "explain": bool(work.get("explain")),
            "meeting": any(r in ("可決", "修正して可決") for r in ((work.get("meeting") or {}).get("results") or {}).values())}
    status = work.get("status", "")
    current = STEP_OF_BUSY.get(status) or STEP_OF_ERROR.get(status) or next(
        (st["key"] for st in steps if not done[st["key"]]), "")
    if status in STEP_OF_BUSY:
        text = "AI が作業しています。下の進み具合で状況を確認できます。"
    elif status in STEP_OF_ERROR:
        text = "うまくいきませんでした。下の内容を確認して、もう一度ボタンを押してください。"
    elif current == "decide":
        text = "「2. 対応が必要な箇所」で推奨・参考の指摘を判断し、「3. 改定案」の「改定案を作る」を押してください。"
    elif current == "draft":
        text = "「3. 改定案」で「改定案を作り直す」を押してください（判断が変わったため）。" if work.get("draft") \
            else "「3. 改定案」で「採用した指摘から改定案を作る」を押してください。"
    elif current == "board":
        text = ("「4. 理事会での検討」で「理事会の検討資料を作る」を押してください。" if not (bstate and work.get("board"))
                else "「4. 理事会での検討」で" + (bstate.get("reason") or "議題ごとの判断を記録してください。"))
    elif current == "explain":
        text = "「5. 住民向けの説明」で「住民向けの説明を作る」を押してください。"
    elif current == "meeting":
        text = "総会が終わったら、「6. 総会の結果と最新の規約」に結果を記録すると、最新の規約を作れます。"
    else:
        text = "すべての段階が済みました。最新の規約を元の規約集の体裁に整え、規約原本と一緒に保管してください。"
    for st in steps:
        st["state"] = "now" if st["key"] == current else ("done" if done[st["key"]] else "todo")
    return {"steps": steps, "current": current, "next": text}



MEETING_RESULTS = ("可決", "修正して可決", "否決", "提案しなかった")


def _doc_title(work: dict, doc: str) -> str:
    if doc != "規約":
        return doc
    titles = [d["title"] for d in work.get("documents", []) if d.get("kind") == "規約"]
    return titles[0] if titles else "管理規約"


def final_amendments(work: dict) -> dict[str, list]:
    """総会に出す改定（理事会で見送ったものを除く）を、文書ごとに分ける。規約が先、細則はその後。"""
    from core.board import apply_to_draft

    draft = _draft(work)
    if draft is None:
        return {}
    paper = _board(work)
    if paper:
        draft = apply_to_draft(draft, paper, work.get("board_decisions", {}))
    out: dict[str, list] = {}
    for a in draft.amendments:
        out.setdefault(a.document or "規約", []).append(a)
    return dict(sorted(out.items(), key=lambda kv: (kv[0] != "規約", kv[0])))


def _edit_key(a) -> str:
    return f"{a.document or '規約'}|{a.article}"


def adopted_by_meeting(work: dict) -> dict[str, list]:
    """総会で可決した改定（修正して可決なら、総会で直した文に差し替える）。"""
    import dataclasses

    meeting = work.get("meeting") or {}
    results, edits = meeting.get("results", {}), meeting.get("edits", {})
    out = {}
    for doc, ams in final_amendments(work).items():
        r = results.get(doc, "")
        if r not in ("可決", "修正して可決"):
            continue
        if r == "修正して可決":
            ams = [dataclasses.replace(a, text=edits[_edit_key(a)]) if edits.get(_edit_key(a), "").strip() else a for a in ams]
        out[doc] = ams
    return out


def final_documents(work_id: str, work: dict) -> list[dict]:
    """最新の規約・細則（総会で可決したもの）。〔選択〕が残っていれば作らない。"""
    from datetime import date

    from core.consolidate import consolidate, wareki
    from core.draft import CHOICE_MARK
    from core.explain import ref_name

    meeting = work.get("meeting") or {}
    adopted = adopted_by_meeting(work)
    if not adopted:
        return []
    corpus = _corpus(work_id)
    held = date.fromisoformat(meeting["date"]) if meeting.get("date") else None
    effective = date.fromisoformat(meeting["effective"]) if meeting.get("effective") else held
    docs = []
    for n, (doc, ams) in enumerate(adopted.items()):
        left = [ref_name(a) for a in ams if CHOICE_MARK in a.text]
        title = _doc_title(work, doc)
        kiyaku = corpus.get(doc)
        blocks = consolidate(kiyaku, ams, title, effective, meeting.get("name", "")) if kiyaku and not left else []
        changed = "・".join(a.article for a in ams)
        history = (f"{meeting.get('name', '総会')}（{wareki(held) if held else '日付未入力'}）"
                   f"{'特別決議' if doc == '規約' else '普通決議'}により改正（{changed}）")
        docs.append({"n": n, "doc": doc, "title": title, "blocks": blocks, "left": left, "count": len(ams),
                     "history": history})
    return docs

def _error_page(request: Request, status: int, message: str):
    """エラーを、画面では日本語のページで示す（API の呼び出しには JSON で返す）。"""
    wants_json = request.url.path.endswith("/status") or "text/html" not in request.headers.get("accept", "")
    if wants_json:
        return JSONResponse({"detail": message}, status_code=status)
    parts = request.url.path.strip("/").split("/")
    back = f"/works/{parts[1]}" if len(parts) > 2 and parts[0] == "works" and status != 404 else "/"
    return templates.TemplateResponse(request, "error.html", {"status": status, "message": message, "back": back},
                                      status_code=status)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else ""
    if not detail or detail.isascii():  # FastAPI 既定の英語のメッセージ（Not Found など）は日本語にする
        detail = "ページが見つかりません。" if exc.status_code == 404 else "この操作はできません。前の画面に戻ってください。"
    return _error_page(request, exc.status_code, detail)


@app.exception_handler(RequestValidationError)
async def form_error(request: Request, exc: RequestValidationError):
    return _error_page(request, 400, "入力が足りないか、正しくありません。前の画面に戻って、入力欄を確認してください。")


@app.exception_handler(store.WorkNotFound)
async def missing_work(request: Request, exc: store.WorkNotFound):
    return _error_page(request, 404, "この作業は見つかりません。削除されたか、アドレスが違う可能性があります。")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"works": store.list_works(), "supported": sorted(SUPPORTED), "samples": SAMPLES})


@app.post("/works")
def create_work(
    name: str = Form(...),
    kind: str = Form("単棟型"),
    units: str = Form(""),
    electronic: str = Form("未定"),
    org: str = Form(""),
    sample: str = Form(""),
    file: UploadFile | None = File(None),
):
    if kind != "単棟型":
        raise HTTPException(400, "現在は単棟型のみに対応しています。")
    if not sample:
        if not file or not file.filename:
            raise HTTPException(400, "規約のファイルを選んでください。")
        suffix = Path(file.filename).suffix.lower()
        if suffix not in SUPPORTED:
            raise HTTPException(400, f"対応していない形式です（対応：{', '.join(sorted(SUPPORTED))}）。")
    work_id = store.new_id()
    d = store.path(work_id)
    d.mkdir(parents=True, exist_ok=True)
    if sample:
        src = SAMPLES.get(sample, SAMPLES["standard"])["path"]
        shutil.copy(src, d / f"source{src.suffix}")
    else:
        with open(d / f"source{suffix}", "wb") as out:
            shutil.copyfileobj(file.file, out)
    try:
        kiyaku = load_kiyaku(_source(work_id))
    except UnsupportedFormat as e:
        shutil.rmtree(d)
        raise HTTPException(400, str(e))
    if len(kiyaku.articles) < 5:
        shutil.rmtree(d)
        msg = "条文を読み取れませんでした。「第1条」のような書き方の規約か確認してください。"
        if not sample and suffix == ".pdf":
            msg += ("PDF の場合、紙をスキャンしただけの PDF（文字を選択できないもの）は読み取れません。"
                    "文字に起こして Word やテキストで保存してから読み込み、点検の前に「現行」の文を原本と見比べてください。")
        raise HTTPException(400, msg)
    from core.ingest import load_collection

    documents = load_collection(_source(work_id)).summary()
    info = {"型": kind, "電磁的方法の利用": electronic}
    if units:
        info["戸数"] = units
    store.save(work_id, {"name": name, "org": org.strip(), "info": info, "status": "点検中", "articles": len(kiyaku.articles),
                         "documents": documents, "log": []})
    threading.Thread(target=_run_review, args=(work_id,), daemon=True).start()
    return RedirectResponse(f"/works/{work_id}", status_code=303)


def next_step(work: dict) -> str:
    """指摘の判断のあとに、次にすることの案内。"""
    from core.progress import draft_plan

    plan = draft_plan(_adopted_count(work))
    cost = f"{plan['estimate']}、AI の費用 {plan['cost']}ほど"
    if plan["large"]:
        cost += "。採用が多いと時間がかかるので、急ぐ場合は推奨・参考を絞ってください"
    if not work.get("draft"):
        return f"判断が終わったら、下の「採用した指摘から改定案を作る」を押してください（改定案に入れる指摘 {plan['adopted']}件で{cost}）。"
    if work.get("draft_stale"):
        return f"今の改定案を作った後に判断が変わりました。下の「改定案を作り直す」を押してください（{cost}）。"
    return "判断は今の改定案に反映されています。「4. 理事会での検討」に進めます。"


def decision_summary(work: dict) -> dict:
    findings = work.get("findings", [])
    decisions = work.get("decisions", {})
    tally = {c: sum(1 for i, f in enumerate(findings)
                    if f["category"] != "必須" and decisions.get(str(i), {}).get("decision") == c) for c in DECISIONS}
    must = sum(1 for f in findings if f["category"] == "必須")
    return {"must": must, "chosen": tally["採用"], "total": must + tally["採用"], "tally": tally,
            "next": next_step(work), "saved_at": work.get("decisions_saved_at", "")}


def _now() -> str:
    from datetime import datetime

    from core.review import JST

    return datetime.now(JST).strftime("%m月%d日 %H:%M")



def _source_note(work_id: str, work: dict) -> dict:
    """読み込んだ元（電子データ／PDF／サンプル）と、「現行」欄について人が確認すること。"""
    from core.quality import SOURCE_NOTES, source_kind

    try:
        suffix = _source(work_id).suffix
    except HTTPException:
        return {"kind": "", "text": ""}
    kind = source_kind(suffix, sample=work.get("name", "").startswith("サンプル："))
    label = {".docx": "Word", ".pdf": "PDF", ".txt": "テキスト", ".md": "テキスト"}.get(suffix.lower(), suffix)
    return {"kind": kind, "label": label, "text": SOURCE_NOTES[kind]}

@app.get("/works/{work_id}", response_class=HTMLResponse)
def show_work(request: Request, work_id: str):
    work = store.load(work_id)
    findings = work.get("findings", [])
    order = {"必須": 0, "推奨": 1, "参考": 2}
    rows = sorted(enumerate(findings), key=lambda x: (order.get(x[1]["category"], 9), x[0]))
    views = {}
    if findings:
        from core.present import view

        try:
            corpus = _corpus(work_id)
        except Exception:  # 表示の補助なので、読み込めなくても画面は出す
            corpus = None
        views = {i: view(f, corpus) for i, f in rows}
    decisions = work.get("decisions", {})
    summary = decision_summary(work)
    return templates.TemplateResponse(request, "work.html", {
        "id": work_id, "work": work, "rows": rows, "views": views, "summary": summary, "tally": summary["tally"], "decisions": decisions, "choices": DECISIONS,
        "choice_help": CHOICE_HELP,
        "board": work.get("board"), "board_decisions": work.get("board_decisions", {}),
        "board_choices": __import__("core.board", fromlist=["DECISIONS"]).DECISIONS,
        "board_tasks": __import__("core.board", fromlist=["TIER_TASK"]).TIER_TASK,
        "board_state": board_state(work) if work.get("draft") else None,
        "board_points": _points(work) if work.get("board") and work.get("draft") else {},
        **_questions_context(work),
        "meeting_groups": final_amendments(work) if work.get("draft") else {},
        "meeting": work.get("meeting") or {},
        "meeting_results": MEETING_RESULTS,
        "finals": final_documents(work_id, work) if work.get("meeting") else [],
        "hist_line": __import__("core.history", fromlist=["line"]).line,
        "progress": progress_view(work) if work["status"] in BUSY else None,
        "journey": journey(work, board_state(work) if work.get("draft") else None),
        "quality": __import__("core.quality", fromlist=["draft_quality"]).draft_quality(work) if work.get("draft") else None,
        "source_note": _source_note(work_id, work),
        "done": request.query_params.get("done", ""),
        "bulk": request.query_params.get("bulk", ""),
    })


def _questions_context(work: dict) -> dict:
    """理事会の欄の「組合が選ぶ点」（問いごとにまとめたもの）と、いまの答え。"""
    from core.board import choice_questions, current_answers, point_key

    if not (work.get("board") and work.get("draft")):
        return {"questions": [], "answers": [], "qindex": {}, "point_key": point_key}
    qs = choice_questions(_points(work))
    return {"questions": qs, "answers": current_answers(qs, work.get("board_decisions", {})),
            "qindex": {q["key"]: k for k, q in enumerate(qs)}, "point_key": point_key}


def progress_view(work: dict) -> dict:
    """処理中の進み具合（段階・件数・経過時間・最後に動きがあってからの秒数・日本語の作業の記録）。"""
    import time

    from core.progress import summarize

    now = time.time()
    since = work.get("status_since") or now
    log = work.get("log", [])
    current = [e for e in log if e.get("ts", 0) >= since - 1]  # この処理の記録だけ
    label = {"session": "開始", "message": "AIのメモ", "found": "指摘", "grading": "採点", "graded": "採点結果",
             "error": "エラー", "tool": "作業", "builtin": "作業", "stopped": "上限", "precedent": "下書き"}
    from core.quality import RESULT_JA

    lines, now_text = [], "準備しています"
    for e in current[-40:]:
        kind, text = e.get("kind"), str(e.get("text", ""))
        if kind in ("tool", "builtin"):
            text = text.split("：", 1)[-1]
        elif kind == "session" and text.startswith("sesn_"):
            text = "AI の作業を始めました"
        elif kind == "graded":  # 採点役のコメントは長く技術的なので、結果だけにする（中身は改定案の欄で見られる）
            head = text.split("：", 1)
            result = head[1] if head[0] == "採点役の確認" else head[0]
            text = "採点役の確認：" + RESULT_JA.get(result.split("：")[0], result.split("：")[0])
        elif kind == "grading" and text.startswith("採点 "):
            text = "採点役が確認しています（" + text.removeprefix("採点 ") + "）"
        elif kind == "message":  # AI のメモは内部の言葉が混じるので、短くして記録にだけ残す
            text = text.replace("\n", " ")[:80] + ("…" if len(text) > 80 else "")
        lines.append({"t": e.get("t", ""), "kind": label.get(kind, kind), "text": text[:300]})
        if kind != "message":
            now_text = text
    last = current[-1]["ts"] if current else since
    return {"elapsed": int(now - since), "last_age": int(now - last), "lines": lines,
            "current": now_text, **summarize(work.get("status", ""), current, adopted=_adopted_count(work))}


def _adopted_count(work: dict) -> int:
    """改定案に入れる指摘の件数（必須＋採用）。"""
    return sum(1 for d in work.get("decisions", {}).values() if d.get("decision") == "採用")


def _cost_entry(step: str, cost) -> dict:
    return {"step": step, "cost": cost, "at": _now()}


@app.get("/works/{work_id}/status")
def work_status(work_id: str):
    work = store.load(work_id)
    return JSONResponse({"status": work["status"], "findings": len(work.get("findings", [])),
                         "progress": progress_view(work) if work["status"] in BUSY else None})


@app.post("/works/{work_id}/decisions")
async def save_decisions(request: Request, work_id: str):
    form = await request.form()
    work = store.load(work_id)
    from core.history import record

    decisions = work.get("decisions", {})
    before = {k: v.get("decision") for k, v in decisions.items()}
    now = _now()
    for i, f in enumerate(work.get("findings", [])):
        key = str(i)
        prev = decisions.get(key, {})
        decision = form.get(f"decision_{i}", prev.get("decision", "保留"))
        if f["category"] == "必須":
            decision = "採用"  # 必須は改定案に自動で入れる（docs/SPEC.md）
        if decision in DECISIONS:
            reason = str(form.get(f"reason_{i}", prev.get("reason", ""))).strip()
            decisions[key] = {"decision": decision, "reason": reason, "history": record(prev, decision, reason, now)}
    changed = before != {k: v.get("decision") for k, v in decisions.items()}
    stale = bool(work.get("draft")) and (changed or work.get("draft_stale", False))
    store.update(work_id, decisions=decisions, draft_stale=stale, decisions_saved_at=now)
    # 保存したら次の工程（改定案）の欄へ移り、保存の結果と次にすることを示す
    return RedirectResponse(f"/works/{work_id}?saved=1#next", status_code=303)



@app.post("/works/{work_id}/org")
async def save_org(request: Request, work_id: str):
    form = await request.form()
    store.load(work_id)
    store.update(work_id, org=str(form.get("org", "")).strip()[:80])
    _rerender(work_id)
    return RedirectResponse(f"/works/{work_id}?done=org", status_code=303)


BULK_SCOPES = {"推奨": ("推奨",), "参考": ("参考",), "推奨・参考": ("推奨", "参考")}


@app.post("/works/{work_id}/decisions/bulk")
async def save_bulk_decisions(request: Request, work_id: str):
    """推奨・参考の指摘を、区分ごとにまとめて判断する（1件ずつ確定する手間を省く）。

    判断が変わる指摘だけ履歴を残す。理由が空なら「まとめて採用」のように残す。
    """
    from core.history import record

    form = await request.form()
    scope, decision = str(form.get("scope", "")), str(form.get("decision", ""))
    if scope not in BULK_SCOPES or decision not in DECISIONS:
        raise HTTPException(400, "まとめて判断する範囲か判断の値が正しくありません。")
    reason = str(form.get("reason", "")).strip() or f"まとめて{decision}"
    work = store.load(work_id)
    decisions = work.get("decisions", {})
    now, changed = _now(), 0
    for i, f in enumerate(work.get("findings", [])):
        if f["category"] not in BULK_SCOPES[scope]:
            continue
        prev = decisions.get(str(i), {})
        if prev.get("decision") == decision:
            continue
        decisions[str(i)] = {"decision": decision, "reason": reason, "history": record(prev, decision, reason, now)}
        changed += 1
    stale = bool(work.get("draft")) and (changed > 0 or work.get("draft_stale", False))
    work.update(decisions=decisions, draft_stale=stale, decisions_saved_at=now)
    store.update(work_id, decisions=decisions, draft_stale=stale, decisions_saved_at=now)
    return JSONResponse(decision_summary(work) | {"changed": changed})


@app.post("/works/{work_id}/decisions/{index}")
async def save_one_decision(request: Request, work_id: str, index: int):
    """指摘1件の判断と理由を保存する（画面で「確定する」を押したとき。ページは移動しない）。

    判断を変えたら履歴を1件追加し、判断を変えずに理由だけ直したら最新の履歴を書き直す。
    """
    from core.history import record

    form = await request.form()
    work = store.load(work_id)
    findings = work.get("findings", [])
    if not 0 <= index < len(findings):
        raise HTTPException(404, "指摘が見つかりません")
    decisions = work.get("decisions", {})
    key = str(index)
    prev = decisions.get(key, {})
    decision = str(form.get("decision", prev.get("decision", "保留")))
    if findings[index]["category"] == "必須":
        decision = "採用"
    if decision not in DECISIONS:
        raise HTTPException(400, "判断の値が正しくありません")
    from core.history import line

    reason = str(form.get("reason", prev.get("reason", ""))).strip()
    now = _now()
    decisions[key] = {"decision": decision, "reason": reason, "history": record(prev, decision, reason, now)}
    stale = bool(work.get("draft")) and (decision != prev.get("decision") or work.get("draft_stale", False))
    work.update(decisions=decisions, draft_stale=stale, decisions_saved_at=now)
    store.update(work_id, decisions=decisions, draft_stale=stale, decisions_saved_at=now)
    item = decisions[key] | {"lines": [line(e) for e in reversed(decisions[key]["history"])]}
    return JSONResponse(decision_summary(work) | {"item": item})


@app.post("/works/{work_id}/draft")
def start_draft(work_id: str):
    work = store.load(work_id)
    if work["status"] in BUSY:
        raise HTTPException(409, "処理中です。終わるまでお待ちください。")
    store.update(work_id, status="改定案作成中")
    threading.Thread(target=_run_draft, args=(work_id,), daemon=True).start()
    return RedirectResponse(f"/works/{work_id}", status_code=303)



@app.post("/works/{work_id}/meeting")
async def save_meeting(request: Request, work_id: str):
    """総会の結果（議案ごとの可決・否決、総会の日、施行日、総会で修正した条の文）を保存する。"""
    form = await request.form()
    work = store.load(work_id)
    groups = final_amendments(work)
    results, edits = {}, {}
    for i, (doc, ams) in enumerate(groups.items()):
        r = str(form.get(f"m_result_{i}", ""))
        results[doc] = r if r in MEETING_RESULTS else ""
        for j, a in enumerate(ams):
            text = str(form.get(f"m_edit_{i}_{j}", "")).replace("\r\n", "\n").strip()
            if text and text != a.text.strip():
                edits[_edit_key(a)] = text
    meeting = {"name": str(form.get("m_name", "")).strip(), "date": str(form.get("m_date", "")).strip(),
               "effective": str(form.get("m_effective", "")).strip(), "results": results, "edits": edits,
               "saved_at": _now()}
    store.update(work_id, meeting=meeting)
    return RedirectResponse(f"/works/{work_id}?done=meeting#meeting", status_code=303)


def _final(work_id: str, n: int) -> dict:
    work = store.load(work_id)
    docs = final_documents(work_id, work)
    if not 0 <= n < len(docs) or not docs[n]["blocks"]:
        raise HTTPException(404, "最新の規約を作れません（総会の結果を保存し、〔選択〕が残っていないか確認してください）")
    return docs[n]


@app.get("/works/{work_id}/final/{n}/view", response_class=HTMLResponse)
def final_html(work_id: str, n: int):
    from core.consolidate import to_html as final_to_html

    d = _final(work_id, n)
    return HTMLResponse(final_to_html(d["blocks"], "確認用の表示です。色の付いた条が今回の改正です（印刷すると色と印は消えます）。"
                                                   "書式は元の規約集に合わせて整えてください。"))


@app.get("/works/{work_id}/final/{n}.docx")
def final_docx(work_id: str, n: int):
    from urllib.parse import quote

    from core.consolidate import to_docx

    d = _final(work_id, n)
    name = quote(f"{d['title']}（最新）.docx")
    return Response(to_docx(d["blocks"]), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f"attachment; filename=\"kiyaku_{n + 1}.docx\"; filename*=UTF-8''{name}"})

@app.get("/works/{work_id}/taisho", response_class=HTMLResponse)
def taisho(work_id: str):
    p = store.path(work_id) / "taisho.html"
    if not p.exists():
        raise HTTPException(404, "新旧対照表はまだありません")
    return FileResponse(p, media_type="text/html; charset=utf-8")


@app.get("/works/{work_id}/taisho.md")
def taisho_md(work_id: str):
    p = store.path(work_id) / "taisho.md"
    if not p.exists():
        raise HTTPException(404, "新旧対照表はまだありません")
    return FileResponse(p, media_type="text/markdown; charset=utf-8", filename="shinkyu_taisho.md")


@app.post("/works/{work_id}/explain")
def start_explain(work_id: str):
    work = store.load(work_id)
    if work["status"] in BUSY:
        raise HTTPException(409, "処理中です。終わるまでお待ちください。")
    if not work.get("draft"):
        raise HTTPException(400, "先に改定案を作ってください。")
    state = board_state(work)
    if not state["ready"]:
        raise HTTPException(400, "住民向けの説明は、理事会での検討が済んでから作ります。" + state["reason"])
    store.update(work_id, status="説明文作成中")
    threading.Thread(target=_run_explain, args=(work_id,), daemon=True).start()
    return RedirectResponse(f"/works/{work_id}", status_code=303)


@app.get("/works/{work_id}/explain", response_class=HTMLResponse)
def explain_page(work_id: str):
    p = store.path(work_id) / "explain.html"
    if not p.exists():
        raise HTTPException(404, "住民向けの説明はまだありません")
    return FileResponse(p, media_type="text/html; charset=utf-8")


@app.post("/works/{work_id}/board")
def start_board(work_id: str):
    work = store.load(work_id)
    if work["status"] in BUSY:
        raise HTTPException(409, "処理中です。終わるまでお待ちください。")
    if not work.get("draft"):
        raise HTTPException(400, "先に改定案を作ってください。")
    store.update(work_id, status="検討資料作成中")
    threading.Thread(target=_run_board, args=(work_id,), daemon=True).start()
    return RedirectResponse(f"/works/{work_id}", status_code=303)


@app.post("/works/{work_id}/board/decisions")
async def save_board_decisions(request: Request, work_id: str):
    from core.board import DECISIONS, NEEDS_REDRAFT, to_html as board_html

    form = await request.form()
    work = store.load(work_id)
    paper = _board(work)
    if not paper:
        raise HTTPException(400, "検討資料がありません。")
    from core.history import record

    old = work.get("board_decisions", {})
    decisions = {}
    changed_redraft = False
    now = _now()
    from core.board import choice_questions, picked_text, point_key

    points = _points(work)
    # 組合が選ぶ点は、問いごとに1回だけ選ぶ（b_q_{問いの番号}）。答えを関係するすべての議題に使う
    answers = {q["key"]: str(form.get(f"b_q_{k}", "")).strip() for k, q in enumerate(choice_questions(points))}
    for i, it in enumerate(paper.items):
        d = str(form.get(f"b_decision_{i}", ""))
        pts = points.get(i, [])
        picked = {str(j): answers.get(point_key(p), "") for j, p in enumerate(pts)}
        entry = {"decision": d if d in DECISIONS[it.tier] else "", "note": str(form.get(f"b_note_{i}", "")).strip(),
                 "choice": picked_text(pts, picked) if pts else str(form.get(f"b_choice_{i}", "")).strip()}
        prev = old.get(str(i), {})
        if entry != {k: prev.get(k, "") for k in entry} and (entry["decision"] in NEEDS_REDRAFT or prev.get("decision") in NEEDS_REDRAFT):
            changed_redraft = True
        if entry["choice"] != prev.get("choice", ""):  # 選んだ案が変われば、改定案に反映し直す
            changed_redraft = True
        if pts:
            entry["picked"] = picked
        entry["history"] = record(prev, entry["decision"], entry["note"], now, reason_key="note",
                                  extra={"choice": entry["choice"]})
        decisions[str(i)] = entry
    changes = {"board_decisions": decisions}
    if changed_redraft:
        changes["draft_reflects_board"] = False
    store.update(work_id, **changes)
    (store.path(work_id) / "board.html").write_text(board_html(paper, decisions, _org(work), points), encoding="utf-8")
    return RedirectResponse(f"/works/{work_id}#board", status_code=303)


@app.post("/works/{work_id}/board/redraft")
def redraft_with_board(work_id: str):
    work = store.load(work_id)
    if work["status"] in BUSY:
        raise HTTPException(409, "処理中です。終わるまでお待ちください。")
    store.update(work_id, status="改定案作成中")
    threading.Thread(target=_run_draft, args=(work_id, True), daemon=True).start()
    return RedirectResponse(f"/works/{work_id}", status_code=303)


@app.get("/works/{work_id}/board", response_class=HTMLResponse)
def board_page(work_id: str):
    p = store.path(work_id) / "board.html"
    if not p.exists():
        raise HTTPException(404, "理事会の検討資料はまだありません")
    return FileResponse(p, media_type="text/html; charset=utf-8")
