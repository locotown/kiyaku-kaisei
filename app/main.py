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
DECISIONS = ("採用", "不採用", "保留")
BUSY = ("点検中", "改定案作成中", "説明文作成中")


def _source(work_id: str) -> Path:
    files = [p for p in store.path(work_id).glob("source.*")]
    if not files:
        raise HTTPException(404, "規約のファイルがありません")
    return files[0]


def _findings(work: dict) -> list[Finding]:
    return [Finding(**f) for f in work.get("findings", [])]


def _run_review(work_id: str) -> None:
    from core.review import run_review

    work = store.load(work_id)
    try:
        kiyaku = load_kiyaku(_source(work_id))
        result = run_review(kiyaku, work["info"], on_event=lambda k, t: store.append_log(work_id, k, t),
                            title=f"点検：{work['name']}")
        decisions = {str(i): {"decision": "採用" if f.category == "必須" else "保留", "reason": ""}
                     for i, f in enumerate(result.findings)}
        store.update(work_id, status="点検済み", findings=[f.to_dict() for f in result.findings],
                     decisions=decisions, summary=result.summary, review_session=result.session_id,
                     review_cost=result.usage.get("list_cost"))
    except Exception as e:
        store.append_log(work_id, "error", f"{type(e).__name__}: {e}")
        store.update(work_id, status="エラー", error=traceback.format_exc(limit=3))


def _run_draft(work_id: str) -> None:
    from core.drafting import run_draft

    work = store.load(work_id)
    try:
        kiyaku = load_kiyaku(_source(work_id))
        adopted = [f for i, f in enumerate(_findings(work)) if work["decisions"][str(i)]["decision"] == "採用"]
        result = run_draft(kiyaku, adopted, work["info"], on_event=lambda k, t: store.append_log(work_id, k, t),
                           title=f"改定案：{work['name']}")
        d = store.path(work_id)
        if result.draft:
            (d / "taisho.html").write_text(to_html(result.draft, kiyaku, f"{work['name']} 新旧対照表（案）"), encoding="utf-8")
            (d / "taisho.md").write_text(to_markdown(result.draft, kiyaku, f"{work['name']} 新旧対照表（案）"), encoding="utf-8")
        store.update(work_id, status="改定案あり" if result.draft else "改定案エラー",
                     draft=result.draft.to_dict() if result.draft else None,
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
        draft = Draft(amendments=[Amendment(**a) for a in work["draft"]["amendments"]], notes=work["draft"]["notes"])
        ex, _ = generate(draft, work["info"])
        (store.path(work_id) / "explain.html").write_text(explain_html(ex, work["name"]), encoding="utf-8")
        store.update(work_id, status="説明文あり", explain=ex.model_dump(), explain_metrics=measure_explanation(ex))
    except Exception as e:
        store.append_log(work_id, "error", f"{type(e).__name__}: {e}")
        store.update(work_id, status="説明文エラー", error=traceback.format_exc(limit=3))


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"works": store.list_works(), "supported": sorted(SUPPORTED)})


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
        shutil.copy(SAMPLE, d / "source.txt")
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
    info = {"型": kind, "電磁的方法の利用": electronic}
    if units:
        info["戸数"] = units
    store.save(work_id, {"name": name, "info": info, "status": "点検中", "articles": len(kiyaku.articles), "log": []})
    threading.Thread(target=_run_review, args=(work_id,), daemon=True).start()
    return RedirectResponse(f"/works/{work_id}", status_code=303)


@app.get("/works/{work_id}", response_class=HTMLResponse)
def show_work(request: Request, work_id: str):
    work = store.load(work_id)
    findings = work.get("findings", [])
    order = {"必須": 0, "推奨": 1, "参考": 2}
    rows = sorted(enumerate(findings), key=lambda x: (order.get(x[1]["category"], 9), x[0]))
    return templates.TemplateResponse(request, "work.html", {
        "id": work_id, "work": work, "rows": rows, "decisions": work.get("decisions", {}), "choices": DECISIONS,
    })


@app.get("/works/{work_id}/status")
def work_status(work_id: str):
    work = store.load(work_id)
    return JSONResponse({"status": work["status"], "log": work.get("log", [])[-30:], "findings": len(work.get("findings", []))})


@app.post("/works/{work_id}/decisions")
async def save_decisions(request: Request, work_id: str):
    form = await request.form()
    work = store.load(work_id)
    decisions = work.get("decisions", {})
    for i, f in enumerate(work.get("findings", [])):
        key = str(i)
        decision = form.get(f"decision_{i}", decisions.get(key, {}).get("decision", "保留"))
        if f["category"] == "必須":
            decision = "採用"  # 必須は改定案に自動で入れる（docs/SPEC.md）
        if decision in DECISIONS:
            decisions[key] = {"decision": decision, "reason": str(form.get(f"reason_{i}", "")).strip()}
    store.update(work_id, decisions=decisions)
    return RedirectResponse(f"/works/{work_id}#findings", status_code=303)


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
    store.update(work_id, status="説明文作成中")
    threading.Thread(target=_run_explain, args=(work_id,), daemon=True).start()
    return RedirectResponse(f"/works/{work_id}", status_code=303)


@app.get("/works/{work_id}/explain", response_class=HTMLResponse)
def explain_page(work_id: str):
    p = store.path(work_id) / "explain.html"
    if not p.exists():
        raise HTTPException(404, "住民向けの説明はまだありません")
    return FileResponse(p, media_type="text/html; charset=utf-8")
