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
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app import store
from core.config import ROOT
from core.findings import Finding
from core.ingest import SUPPORTED, UnsupportedFormat, load_kiyaku
from core.taisho import to_html, to_markdown

app = FastAPI(title="管理規約 改正対応ツール")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
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
                     review_cost=result.usage.get("list_cost"))
    except Exception as e:
        store.append_log(work_id, "error", f"{type(e).__name__}: {e}")
        store.update(work_id, status="エラー", error=traceback.format_exc(limit=3))


def _board(work: dict):
    from core.board import BoardPaper

    return BoardPaper.model_validate(work["board"]) if work.get("board") else None


def _run_draft(work_id: str, with_board: bool = False) -> None:
    from core.board import decisions_text
    from core.drafting import run_draft

    work = store.load(work_id)
    try:
        corpus = _corpus(work_id)
        adopted = [f for i, f in enumerate(_findings(work)) if work["decisions"][str(i)]["decision"] == "採用"]
        board = decisions_text(_board(work), work.get("board_decisions", {})) if with_board and work.get("board") else ""
        result = run_draft(corpus.main, adopted, work["info"], rules=corpus.rules, on_event=lambda k, t: store.append_log(work_id, k, t),
                           title=f"改定案：{work['name']}", board=board)
        d = store.path(work_id)
        if result.draft:
            (d / "taisho.html").write_text(to_html(result.draft, corpus, f"{work['name']} 新旧対照表（案）"), encoding="utf-8")
            (d / "taisho.md").write_text(to_markdown(result.draft, corpus, f"{work['name']} 新旧対照表（案）"), encoding="utf-8")
        extra = {"draft_reflects_board": bool(board), "draft_stale": False} if result.draft else {}
        if result.draft and not board:
            extra.update(board=None, board_decisions={})  # 改定案を作り直したら、理事会の検討資料も作り直す
        store.update(work_id, status="改定案あり" if result.draft else "改定案エラー",
                     draft=result.draft.to_dict() if result.draft else None, **extra,
                     draft_errors=result.errors, draft_evaluations=result.evaluations,
                     draft_session=result.session_id, draft_cost=result.usage.get("list_cost"))
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
        (store.path(work_id) / "explain.html").write_text(explain_html(ex, work["name"], draft), encoding="utf-8")
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
        (store.path(work_id) / "board.html").write_text(board_html(paper, None, work["name"]), encoding="utf-8")
        store.update(work_id, status="検討資料あり", board=paper.model_dump(), board_decisions=default_decisions(paper),
                     draft_reflects_board=False)
    except Exception as e:
        store.append_log(work_id, "error", f"{type(e).__name__}: {e}")
        store.update(work_id, status="検討資料エラー", error=traceback.format_exc(limit=3))


def board_state(work: dict) -> dict:
    """理事会の検討の状態。住民向け説明を作れるかを返す。"""
    from core.board import status

    paper = _board(work)
    if not paper:
        return {"ready": False, "reason": "理事会の検討資料をまだ作っていません。"}
    st = status(paper, work.get("board_decisions", {}))
    if not st["done"]:
        return {**st, "ready": False, "reason": f"まだ判断していない議題が{len(st['undecided'])}つあります。"}
    if st["redraft"] and not work.get("draft_reflects_board"):
        return {**st, "ready": False, "reason": "「修正して採用」「要修正」の議題があります。先に理事会の判断を反映して改定案を作り直してください。"}
    return {**st, "ready": True, "reason": ""}



STEP_OF_BUSY = {"点検中": "review", "改定案作成中": "draft", "検討資料作成中": "board", "説明文作成中": "explain"}
STEP_OF_ERROR = {"エラー": "review", "改定案エラー": "draft", "検討資料エラー": "board", "説明文エラー": "explain"}


def journey(work: dict, bstate: dict | None) -> dict:
    """ページ上部の進め方の案内（済んだ段階・いまの段階・次にすること）。"""
    steps = [{"key": "review", "label": "点検", "anchor": "findings"},
             {"key": "decide", "label": "指摘の判断", "anchor": "findings"},
             {"key": "draft", "label": "改定案", "anchor": "next"},
             {"key": "board", "label": "理事会での検討", "anchor": "board"},
             {"key": "explain", "label": "住民向けの説明", "anchor": "explain"}]
    draft_ok = bool(work.get("draft")) and not work.get("draft_stale")
    done = {"review": bool(work.get("findings")), "decide": bool(work.get("draft")), "draft": draft_ok,
            "board": draft_ok and bool(bstate and bstate.get("ready")), "explain": bool(work.get("explain"))}
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
    else:
        text = "すべての段階が済みました。新旧対照表・検討資料・説明資料を、総会の準備に使えます。"
    for st in steps:
        st["state"] = "now" if st["key"] == current else ("done" if done[st["key"]] else "todo")
    return {"steps": steps, "current": current, "next": text}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"works": store.list_works(), "supported": sorted(SUPPORTED), "samples": SAMPLES})


@app.post("/works")
def create_work(
    name: str = Form(...),
    kind: str = Form("単棟型"),
    units: str = Form(""),
    electronic: str = Form("未定"),
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
        raise HTTPException(400, "条文を読み取れませんでした。「第1条」のような書き方の規約か確認してください。")
    from core.ingest import load_collection

    documents = load_collection(_source(work_id)).summary()
    info = {"型": kind, "電磁的方法の利用": electronic}
    if units:
        info["戸数"] = units
    store.save(work_id, {"name": name, "info": info, "status": "点検中", "articles": len(kiyaku.articles),
                         "documents": documents, "log": []})
    threading.Thread(target=_run_review, args=(work_id,), daemon=True).start()
    return RedirectResponse(f"/works/{work_id}", status_code=303)


def next_step(work: dict) -> str:
    """指摘の判断のあとに、次にすることの案内。"""
    if not work.get("draft"):
        return "判断が終わったら、下の「採用した指摘から改定案を作る」を押してください（10〜15分ほどかかります）。"
    if work.get("draft_stale"):
        return "今の改定案を作った後に判断が変わりました。下の「改定案を作り直す」を押してください。"
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
        "hist_line": __import__("core.history", fromlist=["line"]).line,
        "progress": progress_view(work) if work["status"] in BUSY else None,
        "journey": journey(work, board_state(work) if work.get("draft") else None),
        "done": request.query_params.get("done", ""),
    })


def progress_view(work: dict) -> dict:
    """処理中の進み具合（段階・件数・経過時間・最後に動きがあってからの秒数・日本語の作業の記録）。"""
    import time

    from core.progress import summarize

    now = time.time()
    since = work.get("status_since") or now
    log = work.get("log", [])
    current = [e for e in log if e.get("ts", 0) >= since - 1]  # この処理の記録だけ
    label = {"session": "開始", "message": "AIのメモ", "found": "指摘", "grading": "採点", "graded": "採点結果",
             "error": "エラー", "tool": "作業", "builtin": "作業"}
    lines = []
    for e in current[-40:]:
        text = str(e.get("text", ""))
        if e.get("kind") in ("tool", "builtin"):
            text = text.split("：", 1)[-1]
        elif e.get("kind") == "session" and text.startswith("sesn_"):
            text = "AI の作業を始めました"
        lines.append({"t": e.get("t", ""), "kind": label.get(e.get("kind"), e.get("kind")), "text": text[:300]})
    last = current[-1]["ts"] if current else since
    return {"elapsed": int(now - since), "last_age": int(now - last), "lines": lines,
            "current": lines[-1]["text"] if lines else "準備しています", **summarize(work.get("status", ""), current)}


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
    for i, it in enumerate(paper.items):
        d = str(form.get(f"b_decision_{i}", ""))
        entry = {"decision": d if d in DECISIONS[it.tier] else "", "note": str(form.get(f"b_note_{i}", "")).strip(),
                 "choice": str(form.get(f"b_choice_{i}", "")).strip()}
        prev = old.get(str(i), {})
        if entry != {k: prev.get(k, "") for k in entry} and (entry["decision"] in NEEDS_REDRAFT or prev.get("decision") in NEEDS_REDRAFT):
            changed_redraft = True
        entry["history"] = record(prev, entry["decision"], entry["note"], now, reason_key="note",
                                  extra={"choice": entry["choice"]})
        decisions[str(i)] = entry
    changes = {"board_decisions": decisions}
    if changed_redraft:
        changes["draft_reflects_board"] = False
    store.update(work_id, **changes)
    (store.path(work_id) / "board.html").write_text(board_html(paper, decisions, work["name"]), encoding="utf-8")
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
