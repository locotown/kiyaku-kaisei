"""画面（FastAPI）。

起動:  uv run uvicorn app.main:app --reload
流れ:  規約のアップロード → 点検（進み具合を表示）→ 指摘の採用・不採用 → 改定案と新旧対照表
"""

from __future__ import annotations

import re
import shutil
import threading
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import store
from core.config import ROOT
from core.findings import Finding
from core.ingest import SUPPORTED, UnsupportedFormat, load_kiyaku
from core.taisho import to_html, to_markdown

# 処理中のまま止まった作業を、次にどうすればよいか（処理はこのサーバーのスレッドで動くので、サーバーが止まると処理も止まる）
INTERRUPTED = {
    "点検中": ("エラー", "トップ画面から、規約をもう一度読み込んで点検を始めてください。"),
    "改定案作成中": ("改定案エラー", "「改定案を作る」（または「改定案を作り直す」）をもう一度押してください。"),
    "検討資料作成中": ("検討資料エラー", "「理事会の検討資料を作る」をもう一度押してください。"),
    "説明文作成中": ("説明文エラー", "「住民向けの説明を作る」をもう一度押してください。"),
}


def recover_interrupted() -> list[str]:
    """サーバーの起動時に、処理中のまま残っている作業を「途中で止まった」に切り替える。

    codespace の停止やサーバーの再起動で処理が途中で止まると、状態が「作成中」のまま残り、ボタンが押せなくなるため。
    起動した時点では、このサーバーで動いている処理はないので、処理中の作業はすべて止まったものと分かる。
    デモの録画用に、わざと処理中にしてある架空の作業（demo_busy）は対象にしない。
    """
    fixed = []
    for w in store.list_works():
        def stop_reading(data: dict) -> None:
            for b in data.get("notes", []):
                if b.get("status") == "読み取り中":
                    b["status"] = "中断"
        if any(b.get("status") == "読み取り中" for b in store.load(w["id"]).get("notes", [])):
            store.mutate(w["id"], stop_reading)
        def stop_review(data: dict) -> None:
            for e in (data.get("human_edits") or {}).values():
                if (e.get("review") or {}).get("status") == "確認中":
                    e["review"]["status"] = "中断"
        if any((e.get("review") or {}).get("status") == "確認中" for e in (store.load(w["id"]).get("human_edits") or {}).values()):
            store.mutate(w["id"], stop_review)
        if w["status"] not in INTERRUPTED:
            continue
        work = store.load(w["id"])
        if work.get("demo_busy"):
            continue
        if w["status"] == "改定案作成中" and work.get("draft_mode") == "partial" and work.get("draft"):
            # 対象の条だけの作り直しは、終わるまで改定案を書き換えないので、今の改定案のまま戻す
            store.append_log(w["id"], "error", "対象の条の作り直しが途中で止まりました（サーバーの再起動など）")
            store.update(w["id"], status="説明文あり" if work.get("explain") else ("検討資料あり" if work.get("board") else "改定案あり"),
                         draft_partial={"status": "中断", "at": _now(), "error": "サーバーの再起動などで止まりました。もう一度押してください。"})
            fixed.append(w["id"])
            continue
        status, todo = INTERRUPTED[w["status"]]
        session = _current_session(work) if w["status"] == "改定案作成中" else ""
        if session:
            todo = ("「途中から再開する」を押すと、AI の作業の止まったところから続けます（最初から作り直すより費用を抑えられます）。"
                    "うまくいかないときは「最初から作り直す」を押してください。")
        store.append_log(w["id"], "error", "処理が途中で止まりました（サーバーの再起動など）")
        store.update(w["id"], status=status, interrupted=w["status"], interrupted_session=session,
                     error="処理が途中で止まりました（codespace の停止や、サーバーの再起動などで、AI の作業が中断されました）。\n"
                           + todo + "\nこれまでの判断と、できていた資料はそのまま残っています。止まるまでの AI の費用はかかっています。")
        fixed.append(w["id"])
    return fixed


def _current_session(work: dict) -> str:
    """今回の処理（状態が「作成中」になってから）で始めた AI のセッションの番号。なければ空。

    前に終わった処理のセッションを「再開」すると、古い結果を受け取ってしまうため、始めた時刻で絞る。
    """
    since = work.get("status_since", 0)
    ids = [e["text"] for e in work.get("log", [])
           if e.get("kind") == "session" and str(e.get("text", "")).startswith("sesn_") and e.get("ts", 0) >= since]
    return ids[-1] if ids else ""


def rerender_all() -> None:
    """保存してある資料（新旧対照表・検討資料・住民向け説明）を、今の見た目で作り直す（AI は使わない）。

    印刷の体裁などを直したとき、すでに作ってある作業の資料にも反映するため。処理中の作業は触らない。
    """
    for w in store.list_works():
        if w["status"] in BUSY:
            continue
        try:
            _rerender(w["id"])
        except Exception as e:  # 1つの作業で作り直せなくても、ほかの作業とサーバーの起動は続ける
            store.append_log(w["id"], "error", f"資料の作り直しに失敗しました：{type(e).__name__}")


@asynccontextmanager
async def lifespan(_app):
    recover_interrupted()
    rerender_all()
    yield


app = FastAPI(title="ととのう規約", lifespan=lifespan)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")  # デザイントークンなど
SAMPLE = ROOT / "evals/data/r7_tantou_before.txt"
# 画面で選べるサンプル（すべて公開資料か架空のデータ）
SAMPLES = {
    "standard": {"path": SAMPLE, "name": "サンプル：改正前の標準管理規約（単棟型）",
                 "title": "改正前の標準管理規約", "format": "テキスト",
                 "contents": "規約本体 87か条（細則なし）",
                 "point": "国の標準どおりの規約。改正で必ず直す箇所（必須）が、標準の条番号どおりに見つかるかを確認できます。"},
    "collection": {"path": ROOT / "evals/data/old_collection.txt", "name": "サンプル：細則を含む規約集（架空）",
                   "title": "細則を含む規約集", "format": "テキスト",
                   "contents": "規約 74か条＋細則3種（総会運営・駐車場使用・ペット飼育）＋改正履歴・メモ",
                   "point": "規約と細則を分けて読み込み、細則への指摘（普通決議）や、規約と細則の食い違いを確認できます。"},
    "old": {"path": ROOT / "evals/data/old_style_kiyaku.txt", "name": "サンプル：長く改正していない古い規約（架空）",
            "title": "長く改正していない古い規約", "format": "テキスト",
            "contents": "規約本体 74か条（細則なし。条番号が標準と違う）",
            "point": "条番号が標準管理規約と違っていても、見出しと内容から該当する条を探せるかを確認できます。"},
    "docx": {"path": ROOT / "evals/data/old_collection.docx", "name": "サンプル：Word の規約集（架空）",
             "title": "Word（.docx）の規約集", "format": "Word",
             "contents": "「細則を含む規約集」と同じ内容。改正履歴は表",
             "point": "Word で管理している規約集を、そのまま読み込めるかを確認できます。"},
}
DECISIONS = ("採用", "不採用", "保留")
# 画面に出す言葉（保存する値は 採用／不採用／保留 のまま）。並びは画面の並び
CHOICE_HELP = {"採用": "改定案に入れる", "不採用": "今回は見送る", "保留": "あとで決める"}


def finding_line(e: dict) -> str:
    """指摘の判断の履歴1件を、画面の言葉（改定案に入れる など）で1行にする。保存した値と、理事会・印刷用の履歴の書き方は変えない。"""
    from core.history import line

    def say(v: str) -> str:
        return CHOICE_HELP.get(v, v) if v else "未判断"
    return line({**e, "from": say(e.get("from", "")), "to": say(e["to"])})
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


def _ident(work_id: str, work: dict) -> str:
    """印刷物・Word に入れる、作業と改定案の版の番号（例：ID 0d9663-a1b2c3）。

    書き込んだ紙や直した Word を戻したときに、どの作業の、どの版の改定案から作った資料かを見分けるため。
    改定案が変われば番号も変わる。
    """
    import hashlib
    import json

    draft = _draft(work)  # 保存した形と、作った直後の形がずれないよう、同じ形に整えてから数える
    payload = json.dumps(draft.to_dict(), sort_keys=True, ensure_ascii=False) if draft else ""
    h = hashlib.sha1(payload.encode()).hexdigest()[:6] if draft else "000000"
    return f"ID {work_id[-6:]}-{h}"


def _skipped(work: dict) -> set:
    """理事会で見送りにした改定（新旧対照表では、行の番号を変えずに印を付ける）。"""
    from core.board import skipped_refs

    paper = _board(work)
    # 改定案を渡す：必須の変更も入っている条は、見送りでも総会に出すので印を付けない
    return skipped_refs(paper, work.get("board_decisions", {}), _draft(work)) if paper else set()


def _write_taisho(work_id: str, work: dict, draft, corpus) -> None:
    title = f"{_org(work)} 管理規約 新旧対照表（案）".strip()
    d = store.path(work_id)
    (d / "taisho.html").write_text(to_html(draft, corpus, title, ident=_ident(work_id, work | {"draft": draft.to_dict()}),
                                           edits=work.get("human_edits"), skipped=_skipped(work)), encoding="utf-8")
    (d / "taisho.md").write_text(to_markdown(draft, corpus, title), encoding="utf-8")


def _rerender(work_id: str) -> None:
    """マンション名を変えたら、作ってある資料（新旧対照表・検討資料・住民向け説明）を AI を使わずに書き直す。"""
    from core.board import apply_to_draft
    from core.board import to_html as board_html
    from core.explain import Explanation
    from core.explain import to_html as explain_html

    work = store.load(work_id)
    draft, paper = _draft(work), _board(work)
    d = store.path(work_id)
    if draft and (d / "taisho.html").exists():
        _write_taisho(work_id, work, draft, _corpus(work_id))
    if paper and (d / "board.html").exists():
        (d / "board.html").write_text(board_html(paper, work.get("board_decisions") or None, _org(work), _points(work),
                                                 ident=_ident(work_id, work)),
                                      encoding="utf-8")
    if work.get("explain") and draft and (d / "explain.html").exists():
        shown = apply_to_draft(draft, paper, work.get("board_decisions", {})) if paper else draft
        (d / "explain.html").write_text(explain_html(Explanation.model_validate(work["explain"]), _org(work), shown,
                                                     ident=_ident(work_id, work)),
                                        encoding="utf-8")


def _run_draft(work_id: str, with_board: bool = False, resume: str = "") -> None:
    """改定案を作る。resume にセッションの番号があれば、途中で止まった作業に続きから取り組む。"""
    from core.board import decisions_text
    from core.drafting import resume_draft, run_draft
    from core.progress import draft_plan

    work = store.load(work_id)
    try:
        corpus = _corpus(work_id)
        adopted = [f for i, f in enumerate(_findings(work)) if work["decisions"][str(i)]["decision"] == "採用"]
        board = decisions_text(_board(work), work.get("board_decisions", {})) if with_board and work.get("board") else ""
        log = lambda k, t: store.append_log(work_id, k, t)
        if resume:
            result = resume_draft(corpus.main, adopted, resume, on_event=log, rules=corpus.rules)
        else:
            result = run_draft(corpus.main, adopted, work["info"], rules=corpus.rules, on_event=log,
                               title=f"改定案：{work['name']}", board=board)
        if result.draft:
            kept = _keep_human_edits(work, result.draft)
            if kept:
                store.append_log(work_id, "edit", f"委員会の書き込みで直した文を引き継ぎました（{'、'.join(kept)}）")
            _write_taisho(work_id, work, result.draft, corpus)
        extra = {"draft_reflects_board": bool(board), "draft_stale": False} if result.draft else {}
        if result.draft and board:
            extra["board_applied"] = _board_snapshot(work.get("board_decisions", {}))
        if result.draft and not board:
            extra.update(board=None, board_decisions={})  # 改定案を作り直したら、理事会の検討資料も作り直す
        step = ("改定案（途中から再開）" if resume else "改定案の作り直し" if work.get("draft") else "改定案")
        store.update(work_id, status="改定案あり" if result.draft else "改定案エラー", interrupted="", interrupted_session="",
                     draft=result.draft.to_dict() if result.draft else None, **extra,
                     draft_errors=result.errors, draft_evaluations=result.evaluations,
                     draft_session=result.session_id, draft_cost=result.usage.get("list_cost"),
                     draft_stop=result.stop, draft_elapsed=round(result.elapsed_sec),
                     draft_precedent=result.precedent, draft_checks=result.checks,
                     draft_plan=draft_plan(len(adopted)),
                     costs=store.load(work_id).get("costs", []) + [_cost_entry(step, result.usage.get("list_cost"))])
    except Exception as e:
        store.append_log(work_id, "error", f"{type(e).__name__}: {e}")
        # AI の作業を始めたあとで止まったなら、途中から再開できるようにセッションの番号を残す
        session = _current_session(store.load(work_id))
        store.update(work_id, status="改定案エラー", error=traceback.format_exc(limit=3),
                     interrupted="改定案作成中" if session else "", interrupted_session=session)


def _run_explain(work_id: str) -> None:
    from core.draft import Amendment, Draft
    from core.explain import generate
    from core.explain import to_html as explain_html
    from core.readability import measure_explanation

    work = store.load(work_id)
    try:
        store.append_log(work_id, "session", "住民向けの説明文を作っています")
        from core.board import apply_to_draft, decisions_text

        draft = Draft(amendments=[Amendment(**a) for a in work["draft"]["amendments"]], notes=work["draft"]["notes"])
        paper, decisions = _board(work), work.get("board_decisions", {})
        draft = apply_to_draft(draft, paper, decisions)  # 理事会が見送りにした改定は説明しない
        ex, usage = generate(draft, work["info"], board=decisions_text(paper, decisions), edits=work.get("human_edits"))
        (store.path(work_id) / "explain.html").write_text(explain_html(ex, _org(work), draft, ident=_ident(work_id, work)),
                                                         encoding="utf-8")
        store.update(work_id, status="説明文あり", explain=ex.model_dump(), explain_metrics=measure_explanation(ex), explain_stale=False,
                     explain_stale_reason="", explain_board=_board_snapshot(work.get("board_decisions", {})),
                     costs=store.load(work_id).get("costs", []) + [_usd_cost_entry("住民向け説明", usage)])
    except Exception as e:
        store.append_log(work_id, "error", f"{type(e).__name__}: {e}")
        store.update(work_id, status="説明文エラー", error=traceback.format_exc(limit=3))


def _run_board(work_id: str) -> None:
    from core.board import default_decisions
    from core.board import generate as board_generate
    from core.board import to_html as board_html
    from core.draft import Amendment, Draft

    work = store.load(work_id)
    try:
        store.append_log(work_id, "session", "理事会の検討資料を作っています")
        draft = Draft(amendments=[Amendment(**a) for a in work["draft"]["amendments"]], notes=work["draft"]["notes"])
        paper, usage = board_generate(draft, work["info"], edits=work.get("human_edits"))
        from core.board import choice_points

        (store.path(work_id) / "board.html").write_text(
            board_html(paper, None, _org(work), choice_points(paper, draft), ident=_ident(work_id, work)), encoding="utf-8")
        store.update(work_id, status="検討資料あり", board=paper.model_dump(), board_decisions=default_decisions(paper),
                     draft_reflects_board=False, costs=store.load(work_id).get("costs", []) + [_usd_cost_entry("理事会の検討資料", usage)])
    except Exception as e:
        store.append_log(work_id, "error", f"{type(e).__name__}: {e}")
        store.update(work_id, status="検討資料エラー", error=traceback.format_exc(limit=3))


def _redraft_reason(paper, decisions: dict, titles: list[str], draft) -> str:
    """作り直しが必要な理由を、実際に選んだ判断に合わせて書く（決まり文句で「修正して採用は選んでいない」と迷わせない）。"""
    from core.board import NEEDS_REDRAFT, required_refs
    from core.explain import _ref_key

    must = required_refs(draft) if draft else set()
    parts = []
    for i, it in enumerate(paper.items):
        if it.title not in titles:
            continue
        d = decisions.get(str(i), {})
        if d.get("decision") == "見送り":
            arts = [x for x in it.articles if _ref_key(x) in must]
            parts.append(f"見送った議題「{it.title}」が、法律で必ず必要な変更と同じ条（{'、'.join(arts)}）に入っています。見送った部分だけを取り除きます")
        elif d.get("decision") in NEEDS_REDRAFT:
            parts.append(f"「{it.title}」を「{d['decision']}」にしました。メモの内容を改定案に入れます")
        elif any(h.get("from") == "見送り" for h in d.get("history") or []) and not d.get("picked"):
            parts.append(f"見送っていた議題「{it.title}」を「{d.get('decision')}」に戻しました。その変更を条に入れ直します")
        else:
            parts.append(f"「{it.title}」で、組合が選ぶ点の案を選びました。選んだ案を改定案に入れます")
    return "。".join(parts) + "。ステップ4の「対象の条だけ作り直す」で、改定案を作り直してください。"


def board_state(work: dict) -> dict:
    """理事会の検討の状態。住民向け説明を作れるかを返す。"""
    from core.board import apply_to_draft, remaining_choices, status

    paper = _board(work)
    if not paper:
        return {"ready": False, "needs_redraft": False, "reason": "理事会の検討資料をまだ作っていません。"}
    decisions = work.get("board_decisions", {})
    st = status(paper, decisions, _points(work), _draft(work))
    if st["done"] and not st["redraft"] and not work.get("draft_reflects_board"):
        # 見送りから採用に戻した議題など、作り直しで条に入れ直す必要があるもの
        st["redraft"] = redraft_targets(work)["items"]
    if not st["done"]:
        n_open = len(st["undecided"]) - len(st["needs_choice"])
        reason = f"まだ判断していない議題が{n_open}件あります。" if n_open else ""
        if st["needs_choice"]:
            reason += f"〔選択〕のある議題（{'、'.join(st['needs_choice'])}）は、「組合が選ぶ点」で案を選んでください。"
        return {**st, "ready": False, "needs_redraft": False, "reason": reason}
    if st["redraft"] and not work.get("draft_reflects_board"):
        targets = redraft_targets(work)["items"]
        titles = [t for t in st["redraft"] if t in targets]  # 反映済みの議題は、理由の文に並べない
        if titles:
            st["redraft"] = titles  # 「対象の議題」の一覧も、まだ反映していない議題だけにそろえる
            return {**st, "ready": False, "needs_redraft": True, "reason": _redraft_reason(paper, decisions, titles, _draft(work))}
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
    # who：人が判断するステップ（済んだら「済」の判子）か、AI が作るステップ（済んだらチェック）か
    steps = [{"key": "review", "label": "読み込み", "anchor": "documents", "who": "ai"},
             {"key": "decide", "label": "指摘の判断", "anchor": "findings", "who": "human"},
             {"key": "draft", "label": "改定案", "anchor": "next", "who": "ai"},
             {"key": "board", "label": "理事会で検討", "anchor": "board", "who": "human"},
             {"key": "explain", "label": "住民への説明", "anchor": "explain", "who": "ai"},
             {"key": "meeting", "label": "総会のあと", "anchor": "meeting", "who": "human"}]
    draft_ok = bool(work.get("draft")) and not work.get("draft_stale")
    done = {"review": bool(work.get("findings")), "decide": bool(work.get("draft")), "draft": draft_ok,
            "board": draft_ok and bool(bstate and bstate.get("ready")),
            # 判断が変わったあと、作り直し・保存し直しが済むまでは済みにしない（上の「次にすること」が下の注意と食い違わないように）
            "explain": bool(work.get("explain")) and not work.get("explain_stale"),
            "meeting": any(r in ("可決", "修正して可決") for r in ((work.get("meeting") or {}).get("results") or {}).values())
                       and not work.get("board_changed_after_meeting")}
    status = work.get("status", "")
    # 対象の条だけ作り直す間は、ステップ4（理事会）の続きとして見せる（想定ユーザーで、ステップ3に戻ったように見えた）
    partial = status == "改定案作成中" and work.get("draft_mode") == "partial"
    current = ("board" if partial else STEP_OF_BUSY.get(status)) or STEP_OF_ERROR.get(status) or next(
        (st["key"] for st in steps if not done[st["key"]]), "")
    if status in STEP_OF_BUSY:
        text = "AI が作業しています。この画面で進み具合を確認できます。"
    elif status in STEP_OF_ERROR:
        text = "うまくいきませんでした。内容を確認して、もう一度ボタンを押してください。"
    elif current == "decide":
        text = "推奨・参考の指摘を、改定案に入れるかどうか判断し、「改定案を作る」を押してください。"
    elif current == "draft":
        text = "判断が変わったため、「改定案を作り直す」を押してください。" if work.get("draft") \
            else "「改定案を作る」を押してください。"
    elif current == "board":
        text = ("「理事会の検討資料を作る」を押してください。" if not (bstate and work.get("board"))
                else (bstate.get("reason") or "議題ごとの判断を記録してください。"))
    elif current == "explain":
        text = ("改定案や理事会の判断が変わりました。「説明文を作り直す」を押してください。" if work.get("explain_stale")
                else "「住民向けの説明を作る」を押してください。")
    elif current == "meeting":
        text = ("総会の結果を記録したあとで、改定案や判断が変わりました。総会で可決した内容と合っているか確かめ、"
                "「総会の結果を保存し直す」を押してください。" if work.get("board_changed_after_meeting")
                else "総会が終わったら、議案ごとの結果を記録すると、最新の規約を作れます。")
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

    from core.consolidate import consolidate, left_out, wareki
    from core.draft import CHOICE_MARK
    from core.explain import ref_name

    meeting = work.get("meeting") or {}
    adopted = adopted_by_meeting(work)
    if not adopted:
        return []
    corpus = _corpus(work_id)
    from core.blanks import is_table
    from core.variants import groups as vgroups, picks as vpicks_of

    vpicks = vpicks_of(vgroups(corpus), work.get("variant_choices"))
    held = date.fromisoformat(meeting["date"]) if meeting.get("date") else None
    effective = date.fromisoformat(meeting["effective"]) if meeting.get("effective") else held
    docs = []
    for n, (doc, ams) in enumerate(adopted.items()):
        left = [ref_name(a) for a in ams if CHOICE_MARK in a.text]
        title = _doc_title(work, doc)
        kiyaku = corpus.get(doc)
        pick = vpicks.get(corpus.resolve(doc) or doc, {})   # 今の規約の両案で、組合が選んだ案（計画A）
        blocks = consolidate(kiyaku, ams, title, effective, meeting.get("name", ""), pick) if kiyaku and not left else []
        raw_blanks = blanks_in(blocks)   # 空欄を埋める前（ステップ6の入力欄に使う。計画D3）
        fills = (work.get("final_fills") or {}).get(doc) or {}
        if fills:
            from core.blanks import fill_blocks

            fill_blocks(blocks, fills)
        changed = "・".join(a.article for a in ams)
        history = (f"{meeting.get('name', '総会')}（{wareki(held) if held else '日付未入力'}）"
                   f"{'特別決議' if doc == '規約' else '普通決議'}により改正（{changed}）")
        docs.append({"n": n, "doc": doc, "title": title, "blocks": blocks, "left": left, "count": len(ams),
                     "history": history, "variants": variant_articles(blocks), "blanks": blanks_in(blocks),
                     "blank_slots": blank_slots(raw_blanks, fills, _org(work)),
                     "blank_tables": [x for x in raw_blanks if is_table(x)],
                     "left_out": left_out(kiyaku) if kiyaku else {"notes": [], "tables": [], "table_lines": 0}})
    return docs


# 標準管理規約の両案は「〔ア案〕」の見出しか、「（ア）…の場合」の行で始まる。ふつうの列挙の（ア）（イ）は拾わない
_VARIANT = re.compile(r"^[\s　]*(?:〔([アイウ])案〕|[（(]([アイウ])[）)].*場合[\s　]*$)")
VARIANT_RULE = 3   # 両案の見つけ方を変えたら上げる（作業に保存した結果を使い直さない）
# 別案が本文の同じ行につながったもの（「…選任できることとする場合2　理事及び監事は…」。PDF などから写したとき）
_INLINE_VARIANT = re.compile(r"とする場合[0-9０-９]+[　 ]")
_ART_NO = re.compile(r"^(第[0-9０-９一二三四五六七八九十百]+条(?:の[0-9０-９一二三四五六七八九十]+)?)")


def variant_articles(blocks) -> list[str]:
    """（ア）（イ）や〔ア案〕〔イ案〕のような、どちらかを選ぶ両案が残ったままの条（標準管理規約を写した規約に多い）。
    最新の規約にそのまま残ると規約として使えない（想定ユーザーでの確認で分かった）。"""
    found: dict[str, set] = {}
    for b in blocks:
        if b.kind != "article":
            continue
        no = next((m.group(1) for ln in b.lines for m in [_ART_NO.match(ln.strip())] if m), "")
        if no:
            found.setdefault(no, set()).update(m.group(1) or m.group(2) for ln in b.lines for m in [_VARIANT.match(ln)] if m)
            if any(_INLINE_VARIANT.search(ln) for ln in b.lines):
                found[no].update({"ア", "イ"})
    return [no for no, marks in found.items() if {"ア", "イ"} <= marks]


def variant_view(work_id: str, work: dict) -> dict:
    """ステップ4の「今の規約の両案」：問（改定案で書き直す条は除く）・選んだ案・機械で分けられない両案の条。"""
    from core.sources import normalize_article_ref
    from core.variants import groups

    try:
        corpus = _corpus(work_id)
    except Exception:  # noqa: BLE001  読めないときは出さない
        return {"groups": [], "choices": {}, "manual": [], "open": 0}
    amended = {(corpus.resolve(a.get("document") or "規約") or "規約", normalize_article_ref(a["article"]))
               for a in (work.get("draft") or {}).get("amendments", [])}
    gs = groups(corpus, amended)
    choices = work.get("variant_choices") or {}
    in_groups = {f"第{n.replace('の', '条の', 1)}" if "の" in n else f"第{n}条" for g in gs if g["doc"] == "規約" for n in g["articles"] + g["amended"]}
    manual = [x for x in current_variants(work_id, work) if x not in in_groups]
    chosen = {(f"第{n.replace('の', '条の', 1)}" if "の" in n else f"第{n}条") for g in gs if g["doc"] == "規約" and choices.get(g["key"])
              for n in g["articles"]}
    # 理事会が改定案の〔選択〕で選んだ案のうち、電磁的方法に関わるもの（作り直したあとも記録に残る）。両案の問と方針をそろえてもらう
    elec = list(dict.fromkeys(v for d in (work.get("board_decisions") or {}).values() for v in (d.get("picked") or {}).values()
                              if v and "電磁的方法" in v))
    return {"groups": gs, "choices": choices, "manual": manual, "chosen": sorted(chosen), "elec_picks": elec,
            "open": sum(1 for g in gs if not choices.get(g["key"]))}


def latest_corpus(work_id: str, work: dict | None = None):
    """総会で可決した改定を反映した最新の規約（最新の規約の画面・Word と同じ文）を、条ごとに読み直した Corpus。
    最新の規約を作れない（総会の結果がない・〔選択〕が残る）ときは None。改定のない細則は元のまま。"""
    from core.consolidate import to_text
    from core.corpus import MAIN
    from core.split import split_kiyaku

    work = work or store.load(work_id)
    docs = [d for d in (final_documents(work_id, work) if work.get("meeting") else []) if d["blocks"]]
    if not docs:
        return None
    corpus = _corpus(work_id)
    for d in docs:
        k = split_kiyaku(to_text(d["blocks"]).splitlines())
        name = corpus.resolve(d["doc"])
        if name == MAIN:
            corpus.main = k
        elif name:
            corpus.rules[name] = k
    return corpus


def has_latest(work_id: str) -> bool:
    """相談で「最新の規約で照らす」を選べるか（総会で可決した改定があり、〔選択〕が残っていない）。"""
    from core.draft import CHOICE_MARK

    try:
        work = store.load(work_id)
    except store.WorkNotFound:
        return False
    adopted = adopted_by_meeting(work) if work.get("meeting") else {}
    return bool(adopted) and not any(CHOICE_MARK in a.text for ams in adopted.values() for a in ams)


def current_variants(work_id: str, work: dict) -> list[str]:
    """今の規約（読み込んだ原本）に、両案が残ったままの条。点検の結果の画面で早めに知らせる。"""
    if "variants" in work and work.get("variants_rule") == VARIANT_RULE:
        return work["variants"]
    from core.consolidate import Block, _article_lines

    try:
        arts = _corpus(work_id).main.articles
    except Exception:  # noqa: BLE001  読めないときは知らせないだけ
        return []
    v = variant_articles([Block("article", _article_lines(a)) for a in arts])
    if work.get("status") not in BUSY:      # AI の処理中は書かない（裏の処理の書き込みと競合させない）
        store.mutate(work_id, lambda d: d.update(variants=v, variants_rule=VARIANT_RULE))
    return v


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
    version: str = Form(""),
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
    from core.readcheck import VERSION_ANSWERS

    store.save(work_id, {"name": name, "org": org.strip(), "info": info, "status": "点検中", "articles": len(kiyaku.articles),
                         "documents": documents, "log": [],
                         # 読み込んだ規約が今有効な版か（課題①）。サンプルは今有効な版として扱う
                         "version": "はい" if sample else (version if version in VERSION_ANSWERS else "")})
    threading.Thread(target=_run_review, args=(work_id,), daemon=True).start()
    return RedirectResponse(f"/works/{work_id}", status_code=303)


def next_step(work: dict) -> str:
    """指摘の判断のあとに、次にすることの案内。"""
    if work.get("status") in BUSY:
        return "AI が作業しています。終わると、画面が自動で切り替わります。"
    from core.progress import draft_plan

    plan = draft_plan(_adopted_count(work))
    cost = f"{plan['estimate']}、AI の費用 {plan['cost']}ほど"
    if plan["large"]:
        cost += "。採用が多いと時間がかかるので、急ぐ場合は推奨・参考を絞ってください"
    if not work.get("draft"):
        return f"判断が終わったら「改定案を作る」を押してください（改定案に入れる指摘 {plan['adopted']}件で{cost}）。"
    if work.get("draft_stale"):
        return f"今の改定案を作った後に判断が変わりました。「改定案を作り直す」を押してください（{cost}）。"
    return "判断は今の改定案に反映されています。次は理事会での検討です。"


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
    from core.board import DECISIONS as BOARD_DECISIONS
    from core.board import TIER_TASK
    from core.history import line as hist_line
    from core.quality import draft_quality

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
        # 同じ見出しの指摘が並ぶときは、対象を見出しに書き加えて見分けられるようにする（想定ユーザーでの確認で分かった）
        from collections import Counter

        dup = Counter(v["title"] for v in views.values())
        for v in views.values():
            if dup[v["title"]] > 1 and v.get("target"):
                v["title"] = f"{v['title']}（{v['target']}）"
    decisions = work.get("decisions", {})
    summary = decision_summary(work)
    return templates.TemplateResponse(request, "work.html", {
        "id": work_id, "work": work, "rows": rows, "views": views, "summary": summary, "tally": summary["tally"], "decisions": decisions, "choices": DECISIONS,
        "choice_help": CHOICE_HELP,
        "board": work.get("board"), "board_decisions": work.get("board_decisions", {}),
        "board_choices": BOARD_DECISIONS,
        "board_tasks": TIER_TASK,
        "board_state": board_state(work) if work.get("draft") else None,
        "board_points": _points(work) if work.get("board") and work.get("draft") else {},
        **_questions_context(work),
        "meeting_groups": final_amendments(work) if work.get("draft") else {},
        "meeting": work.get("meeting") or {},
        "meeting_results": MEETING_RESULTS,
        "finals": final_documents(work_id, work) if work.get("meeting") else [],
        "hist_line": hist_line,
        "finding_line": finding_line,
        "progress": progress_view(work) if work["status"] in BUSY else None,
        "journey": journey(work, board_state(work) if work.get("draft") else None),
        "quality": draft_quality(work) if work.get("draft") else None,
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
             "error": "エラー", "tool": "作業", "builtin": "作業", "stopped": "上限", "precedent": "下書き",
             "resume": "再開", "setup": "準備", "writing": "作業", "edit": "反映"}
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
            result = head[1] if head[0] in ("採点役の確認", "確認役の確認") else head[0]
            text = "確認役の AI の確認：" + RESULT_JA.get(result.split("：")[0], result.split("：")[0])
        elif kind == "grading" and text.startswith("採点 "):
            text = "確認役の AI が確かめています（" + text.removeprefix("採点 ") + "）"
        elif kind == "message":  # AI のメモは内部の言葉が混じるので、短くして記録にだけ残す
            if not re.search(r"[ぁ-んァ-ヶ一-龥]", text):  # 英語だけのメモは出さない（画面はすべて日本語。想定ユーザーでの確認で見つかった）
                continue
            text = text.replace("\n", " ")[:80] + ("…" if len(text) > 80 else "")
        lines.append({"t": e.get("t", ""), "kind": label.get(kind, kind), "text": text[:300]})
        if kind != "message":
            now_text = text
    last = current[-1]["ts"] if current else since
    return {"elapsed": int(now - since), "last_age": int(now - last), "lines": lines,
            "current": now_text, **summarize(work.get("status", ""), current, adopted=_adopted_count(work),
                                             partial=work.get("draft_mode") == "partial")}


def _adopted_count(work: dict) -> int:
    """改定案に入れる指摘の件数（必須＋採用）。"""
    return sum(1 for d in work.get("decisions", {}).values() if d.get("decision") == "採用")


def _cost_entry(step: str, cost) -> dict:
    return {"step": step, "cost": cost, "at": _now()}


def _usd_cost_entry(step: str, usage: dict) -> dict:
    """Messages API の使用量から、費用の記録を作る（公開価格での概算。合計に入れるため）。"""
    from core.notes import cost_usd

    return _cost_entry(step, {"amount": max(1, round(cost_usd(usage or {}) * 100)), "currency": "USD"})


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
    fields = {"org": str(form.get("org", "")).strip()[:80]}
    name = str(form.get("name", "")).strip()[:80]
    if name:                                     # 作業の名前（空なら変えない。サンプルから始めた作業も名前を付け直せるように）
        fields["name"] = name
    store.update(work_id, **fields)
    _rerender(work_id)
    return RedirectResponse(f"/works/{work_id}?done=org", status_code=303)


def blank_view(work_id: str, work: dict) -> list[dict]:
    """ステップ4の「空欄に入れる数字」：改定案の条ごとの空欄と、入れた数字・今の規約の数字（計画D3）。

    空欄を埋めた文は「委員会で直した文」として改定案に入れる。埋める前の文（template）を残し、入れ直し・消すときに使う。
    その後に文が変わった（作り直し・条の文を直す）ときは、前の記録を使わない。
    """
    from core.blanks import lines, slots, suggest
    from core.sources import normalize_article_ref

    draft = work.get("draft") or {}
    fills = work.get("blank_fills") or {}
    corpus = None
    out, row = [], {x["where"]: x["n"] for x in draft_blanks(work)}
    for am in draft.get("amendments") or []:
        if am.get("kind") == "削除":
            continue
        doc = am.get("document") or "規約"
        key = f"{doc}|{am['article']}"
        rec = fills.get(key)
        valid = rec and rec.get("filled") == am["text"]
        template = rec["template"] if valid else am["text"]
        ss = slots(template)
        if not ss:
            continue
        if corpus is None:
            corpus = _corpus(work_id)
        old = "\n".join(a.text() for a in corpus.find(doc, normalize_article_ref(am["before_article"]))) if am.get("before_article") else ""
        sug = suggest(template, old) if old else [""] * len(ss)
        values = (rec.get("values") or []) if valid else []
        for s_ in ss:
            s_["value"] = values[s_["i"]] if s_["i"] < len(values) else ""
            s_["suggest"] = sug[s_["i"]] if s_["i"] < len(sug) else ""
        where = (f"{doc} " if doc != "規約" else "") + am["article"]
        out.append({"key": key, "where": where, "caption": am.get("caption", ""), "slots": ss, "n": row.get(where), "lines": lines(template),
                    "left": sum(1 for x in ss if not x["value"])})
    return out


@app.post("/works/{work_id}/blanks")
async def save_blanks(request: Request, work_id: str):
    """ステップ4で入れた空欄の数字を、改定案の条に入れる（AI は使わない。委員会で直した文として記録する。計画D3）。"""
    from core.blanks import fill

    form = await request.form()
    work = store.load(work_id)
    if work["status"] in BUSY:
        raise HTTPException(409, "AI が作業中です。終わってから入れてください。")
    view = {v["key"]: v for v in blank_view(work_id, work)}
    fills = dict(work.get("blank_fills") or {})
    edits = []
    for am in (work.get("draft") or {}).get("amendments") or []:
        key = f"{am.get('document') or '規約'}|{am['article']}"
        v = view.get(key)
        if not v or not any(f"k_{key}_{x['i']}" in form for x in v["slots"]):
            continue
        rec = fills.get(key)
        template = rec["template"] if rec and rec.get("filled") == am["text"] else am["text"]
        values = [str(form.get(f"k_{key}_{x['i']}", "")).strip()[:20] for x in v["slots"]]
        text = fill(template, values)
        if text == am["text"]:
            continue
        filled = [f"{x['before'].lstrip('…')[-6:]}{val}{x['after'].rstrip('…')[:4]}" for x, val in zip(v["slots"], values) if val]
        edits.append({"document": am.get("document") or "規約", "article": am["article"], "text": text,
                      "note": "空欄（○）に数字を入れた：" + ("、".join(filled) if filled else "入れた数字を消した")})
        fills[key] = {"template": template, "values": values, "filled": text, "at": _now()}
    if edits:
        store.update(work_id, blank_fills=fills)
        _edit_articles(work_id, edits, f"{_now()} 空欄（○）に数字を入れました")
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse({"ok": True, "saved_at": _now(), "changed": [e["article"] for e in edits]})
    return RedirectResponse(f"/works/{work_id}?done=blanks#blanks", status_code=303)


@app.post("/works/{work_id}/final-blanks")
async def save_final_blanks(request: Request, work_id: str):
    """ステップ6：最新の規約に残る空欄（今の規約から引き継いだもの）に入れる数字を保存する。
    改定ではなく、原本の数字を写す作業。最新の規約の画面と Word に入る（計画D3）。"""
    form = await request.form()
    store.load(work_id)
    got: dict[str, dict[str, list[str]]] = {}
    for k, v in form.items():
        if not k.startswith("f|"):
            continue
        _, doc, where, i = k.split("|", 3)
        got.setdefault(doc, {}).setdefault(where, {})[int(i)] = str(v).strip()[:30]

    def fn(d):
        ff = dict(d.get("final_fills") or {})
        for doc, places in got.items():
            cur = dict(ff.get(doc) or {})
            for where, vals in places.items():
                cur[where] = [vals.get(i, "") for i in range(max(vals) + 1)]
            ff[doc] = cur
        d["final_fills"] = ff
    store.mutate(work_id, fn)
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse({"ok": True, "saved_at": _now()})
    return RedirectResponse(f"/works/{work_id}?done=final-blanks#finals", status_code=303)


@app.post("/works/{work_id}/variants")
async def save_variants(request: Request, work_id: str):
    """今の規約の両案で、組合が選んだ案を保存する（AI は使わない。最新の規約を作るときに、選んだ案だけを残す）。"""
    from core.variants import groups

    form = await request.form()
    store.load(work_id)
    valid = {g["key"]: {o["mark"] for o in g["options"]} for g in groups(_corpus(work_id))}
    picked = {k[2:]: str(v) for k, v in form.items() if k.startswith("v_") and k[2:] in valid}

    def fn(d):
        ch = dict(d.get("variant_choices") or {})
        for k, v in picked.items():
            if v in valid[k]:
                ch[k] = v
            else:
                ch.pop(k, None)                    # 「まだ選ばない」に戻す
        d["variant_choices"] = ch
        d.setdefault("variant_history", []).append({"at": _now(), "picked": picked})
    store.mutate(work_id, fn)
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse({"ok": True, "saved_at": _now(), "choices": store.load(work_id).get("variant_choices", {})})
    return RedirectResponse(f"/works/{work_id}?done=variants#variants", status_code=303)


BULK_SCOPES = {"推奨": ("推奨",), "参考": ("参考",), "推奨・参考": ("推奨", "参考"),
               "足す": ("推奨", "参考")}   # 足す：必須以外で、今の規約に定めがない指摘（ステップ2の「足す」の表）


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
    # 理由が空なら、画面の言葉（「今回は見送る」など）で残す
    reason = str(form.get("reason", "")).strip() or f"まとめて「{CHOICE_HELP.get(decision, decision)}」"
    work = store.load(work_id)
    decisions = work.get("decisions", {})
    now, changed = _now(), 0
    only_open = form.get("only_open") == "1"  # まだ決めていない（あとで決める）ものだけ。1件ずつ決めた判断を上書きしない
    for i, f in enumerate(work.get("findings", [])):
        if f["category"] not in BULK_SCOPES[scope]:
            continue
        if scope == "足す" and (f.get("current_excerpt") or "").strip():
            continue
        prev = decisions.get(str(i), {})
        if prev.get("decision") == decision:
            continue
        if only_open and prev.get("decision") in ("採用", "不採用"):
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
    reason = str(form.get("reason", prev.get("reason", ""))).strip()
    now = _now()
    decisions[key] = {"decision": decision, "reason": reason, "history": record(prev, decision, reason, now)}
    stale = bool(work.get("draft")) and (decision != prev.get("decision") or work.get("draft_stale", False))
    work.update(decisions=decisions, draft_stale=stale, decisions_saved_at=now)
    store.update(work_id, decisions=decisions, draft_stale=stale, decisions_saved_at=now)
    item = decisions[key] | {"lines": [finding_line(e) for e in reversed(decisions[key]["history"])]}
    from core.progress import draft_plan

    pl = draft_plan(_adopted_count(work))
    return JSONResponse(decision_summary(work) | {"item": item, "ai_draft": ai_note("redraft" if work.get("draft") else "draft", work),
                                                  "draft_plan": f"改定案づくりは 約{pl['estimate']}・AI の費用 {pl['cost']}ほど（入れる指摘 {pl['adopted']}件）"})


@app.post("/works/{work_id}/draft")
def start_draft(work_id: str):
    work = store.load(work_id)
    if work["status"] in BUSY:
        raise HTTPException(409, "処理中です。終わるまでお待ちください。")
    store.update(work_id, status="改定案作成中", draft_with_board=False, draft_mode="full")
    threading.Thread(target=_run_draft, args=(work_id,), daemon=True).start()
    return RedirectResponse(f"/works/{work_id}", status_code=303)


@app.post("/works/{work_id}/draft/resume")
def resume_draft_work(work_id: str):
    """途中で止まった改定案づくりを、AI のセッションにつなぎ直して続きから進める（最初から作り直すより費用を抑えられる）。"""
    work = store.load(work_id)
    if work["status"] in BUSY:
        raise HTTPException(409, "処理中です。終わるまでお待ちください。")
    session = work.get("interrupted_session", "")
    if work["status"] != "改定案エラー" or not session:
        raise HTTPException(409, "途中から再開できる作業がありません。「改定案を作る」から始めてください。")
    store.update(work_id, status="改定案作成中", draft_mode="full")
    threading.Thread(target=_run_draft, args=(work_id, bool(work.get("draft_with_board")), session), daemon=True).start()
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
    if not any(results.values()):  # 結果を1つも選んでいないときは保存しない（できていた最新の規約を黙って消さない）
        return RedirectResponse(f"/works/{work_id}?done=meeting_empty#meeting", status_code=303)
    meeting = {"name": str(form.get("m_name", "")).strip(), "date": str(form.get("m_date", "")).strip(),
               "effective": str(form.get("m_effective", "")).strip(), "results": results, "edits": edits,
               "saved_at": _now()}
    store.update(work_id, meeting=meeting, board_changed_after_meeting="", board_changed_reason="",
                 meeting_board=_board_snapshot(store.load(work_id).get("board_decisions", {})))
    # 結果を1つも選んでいないときは「保存しました」と出さず、選ぶよう知らせる（何も入れずに終えたと思い込まないように）
    done = "meeting" if any(results.values()) else "meeting_empty"
    return RedirectResponse(f"/works/{work_id}?done={done}#meeting", status_code=303)


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
    v = d.get("variants") or variant_articles(d["blocks"])
    warn = (f"【注意】どちらかを選ぶ両案（（ア）（イ）など）が残っている条があります：{'、'.join(v)}。作業の画面の「4. 理事会で検討」の"
            "「今の規約の両案」で採用している案を選ぶと、その案だけが残ります。選べない形の条は、Word で保存したあとに採用している案だけを残してください。") if v else ""
    return HTMLResponse(final_to_html(d["blocks"], warn + "確認用の表示です。色の付いた条が今回の改正です（印刷すると色と印は消えます）。"
                                                   "書式は元の規約集に合わせて整えてください。", word_href=f"../{n}.docx",
                                      ident=_ident(work_id, store.load(work_id))))


@app.get("/works/{work_id}/final/{n}.docx")
def final_docx(work_id: str, n: int):
    from urllib.parse import quote

    from core.consolidate import to_docx

    d = _final(work_id, n)
    name = quote(f"{d['title']}（最新）.docx")
    return Response(to_docx(d["blocks"], ident=_ident(work_id, store.load(work_id))), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    headers={"Content-Disposition": f"attachment; filename=\"kiyaku_{n + 1}.docx\"; filename*=UTF-8''{name}"})

def read_check(work_id: str) -> dict:
    """ステップ1の「読み込んだ版の確かめ」：改正の記録に出てくる条と、条の中のメモらしい文（課題①②。AI は使わない）。"""
    from core.ingest import load_collection
    from core.readcheck import view

    try:
        return view(load_collection(_source(work_id)))
    except Exception:
        return {"memos": [], "history": {"entries": [], "count": 0, "articles": []}, "has_history": False, "documents": []}


templates.env.globals["read_check"] = read_check


@app.post("/works/{work_id}/version")
async def save_version(request: Request, work_id: str):
    """読み込んだ規約が今有効な版か、の答えを保存する（課題①）。"""
    from core.readcheck import VERSION_ANSWERS

    form = await request.form()
    v = str(form.get("version", ""))
    store.load(work_id)
    store.update(work_id, version=v if v in VERSION_ANSWERS else "")
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse({"ok": True})
    return RedirectResponse(f"/works/{work_id}#readcheck", status_code=303)


_TAIOU_CACHE: dict = {}


def _taiou(work_id: str) -> dict:
    """条の対応表（文の似かたの計算に1〜2秒かかるので、読み込んだファイルが同じ間は使い回す）。"""
    from core.sources import standard
    from core.taiou import match

    src = _source(work_id)
    fixed = store.load(work_id).get("minaoshi_map") or {}   # 人が選び直した対応（計画E3-4）
    key = (work_id, src.stat().st_mtime, tuple(sorted(fixed.items())))
    if key not in _TAIOU_CACHE:
        _TAIOU_CACHE.clear() if len(_TAIOU_CACHE) > 20 else None
        _TAIOU_CACHE[key] = match(_corpus(work_id).main, standard(), fixed)
    return _TAIOU_CACHE[key]


def _touched(work: dict) -> set:
    """今回の改定案（①）で直す、今の規約の条の番号。"""
    from core.sources import normalize_article_ref

    return {normalize_article_ref(a["before_article"]) for a in (work.get("draft") or {}).get("amendments") or []
            if a.get("before_article") and (a.get("document") or "規約") == "規約"}


def _added(work: dict) -> set:
    """今回の改定案（①）で新しく足す、規約の条の番号（標準管理規約の条番号と同じ形）。"""
    from core.sources import normalize_article_ref

    out = set()
    for a in (work.get("draft") or {}).get("amendments") or []:
        if a.get("kind") == "新設" and (a.get("document") or "規約") == "規約":
            out.add(normalize_article_ref(a["article"]))
            if a.get("caption"):   # 条番号が標準とずれた規約では番号が合わないので、見出しでも照らし合わせる
                out.add("見出し:" + re.sub(r"[\s　()（）]", "", a["caption"]))
    return out


@app.get("/works/{work_id}/minaoshi", response_class=HTMLResponse)
def minaoshi_page(request: Request, work_id: str):
    """②これからの見直し（計画E2a）：違いの量・構成表・条の対応表と理事会の判断・決めたことの一覧。AI は使わない。"""
    from core.kozo import build
    from core.minaoshi import ACTIONS, KEEP, added_now, rows, state, summary, valid

    work = store.load(work_id)
    t = _taiou(work_id)
    rs = rows(t, _touched(work), _added(work))
    dec = {r["id"]: v for r in rs if (v := valid(r["type"], (work.get("minaoshi") or {}).get(r["id"])))}
    k = build(_corpus(work_id))
    return templates.TemplateResponse(request, "minaoshi.html", {
        "id": work_id, "work": work, "counts": t["counts"], "rows": rs, "dec": dec, "sum": summary(rs, dec),
        "states": {r["id"]: state(dec.get(r["id"])) for r in rs}, "actions": ACTIONS, "keep": KEEP,
        "added_now": added_now(t, _added(work)), "std_all": t["std_all"],
        "cur_all": [{"number": r["number"], "label": r["label"], "caption": r["caption"]} for r in t["rows"]],
        "mapped": request.query_params.get("mapped", ""),
        "kozo": {"rows": len(k["rows"]), "missing": len(k["missing"]), "bad": len(k["bad_cites"])}})


@app.post("/works/{work_id}/minaoshi")
async def save_minaoshi(request: Request, work_id: str):
    """②の判断を1行ずつ保存する（選ぶとすぐ保存。空の判断は「まだ決めていない」に戻す）。"""
    from core.minaoshi import clean, rows, summary

    form = await request.form()
    rid = str(form.get("id", ""))
    work = store.load(work_id)
    rs = rows(_taiou(work_id), _touched(work), _added(work))
    row = next((r for r in rs if r["id"] == rid), None)
    if row is None:
        raise HTTPException(400, "その行は見つかりません。画面を開き直してください。")
    d, w = clean(row["type"], str(form.get("d", "")), str(form.get("w", "")))
    memo = str(form.get("m", "")).strip()[:300] if d else ""   # 未判断に戻したらメモも消す（見えないメモが残っていた）

    def fn(data):
        m = dict(data.get("minaoshi") or {})
        if d:
            m[rid] = {"d": d, "w": w, "m": memo, "at": _now()}
        else:
            m.pop(rid, None)
        data["minaoshi"] = m
    work = store.mutate(work_id, fn)
    if "application/json" in request.headers.get("accept", ""):
        return JSONResponse({"ok": True, "saved_at": _now(), **summary(rs, work.get("minaoshi") or {})})
    return RedirectResponse(f"/works/{work_id}/minaoshi#r-{rid}", status_code=303)


@app.get("/works/{work_id}/minaoshi/shukudai", response_class=HTMLResponse)
def minaoshi_print(work_id: str):
    """見直しの宿題の検討表（計画E3-1。印刷用）：宿題の条を、今の規約と標準管理規約の文を並べて、理事会の書き込み欄と一緒に。"""
    from core.minaoshi import rows, summary, to_html

    work = store.load(work_id)
    rs = rows(_taiou(work_id), _touched(work), _added(work))
    s = summary(rs, work.get("minaoshi") or {})
    title = f"{_org(work)} 規約の見直し 宿題の検討表".strip()
    return HTMLResponse(to_html(s, title, _ident(work_id, work), _org(work) or work.get("name", ""), _today_wareki()))


@app.post("/works/{work_id}/minaoshi/map")
async def save_minaoshi_map(request: Request, work_id: str):
    """対応する標準管理規約の条を、人が選び直す（計画E3-4。AI は使わない）。
    c＝今の規約の条番号、s＝標準管理規約の条番号（"none" は当たる条がない、"auto" は自動の対応づけに戻す）。
    選び直した行の判断は、行の種類が変わることがあるので消す。"""
    form = await request.form()
    c, sn = str(form.get("c", "")), str(form.get("s", ""))
    if not c or not sn:
        raise HTTPException(400, "対応する条を選んでから押してください。")
    sn = "" if sn == "none" else sn   # 画面では「当たる条はない」を none で送る（空は「まだ選んでいない」と区別するため）
    t = _taiou(work_id)
    if c not in {r["number"] for r in t["rows"]}:
        raise HTTPException(400, "その条は見つかりません。画面を開き直してください。")
    if sn not in ("", "auto") and sn not in {x["number"] for x in t["std_all"]}:
        raise HTTPException(400, "その標準管理規約の条は見つかりません。")

    def fn(data):
        m = dict(data.get("minaoshi_map") or {})
        if sn == "auto":
            m.pop(c, None)
        else:
            m[c] = sn
        data["minaoshi_map"] = m
        dec = dict(data.get("minaoshi") or {})
        dec.pop(f"c{c}", None)
        if sn:
            dec.pop(f"s{sn}", None)
        data["minaoshi"] = dec
    store.mutate(work_id, fn)
    return RedirectResponse(f"/works/{work_id}/minaoshi?mapped=c{c}#r-c{c}", status_code=303)


def _today_wareki() -> str:
    from datetime import date

    from core.consolidate import wareki

    return wareki(date.today())


@app.get("/works/{work_id}/taiou", response_class=HTMLResponse)
def taiou(work_id: str):
    """今の規約と標準管理規約の条の対応表（計画E1。AI は使わない）。全部改正を考える材料。"""
    from core.sources import normalize_article_ref, standard
    from core.taiou import match, to_html

    work = store.load(work_id)
    t, touched = _taiou(work_id), _touched(work)
    title = f"{_org(work)} 管理規約と標準管理規約の条の対応表".strip()
    return HTMLResponse(to_html(t, title, ident=_ident(work_id, work), touched=touched))


@app.get("/works/{work_id}/kozo", response_class=HTMLResponse)
def kozo(work_id: str):
    """規約集の構成表（計画F1。AI は使わない）：読み込んだ文書、規約がほかの決まりに任せている事項と対応する細則、細則が引く規約の条。"""
    from core.kozo import build, to_html

    work = store.load(work_id)
    from core.ingest import load_collection

    try:
        fresh = load_collection(_source(work_id)).summary()   # 今の分け方で（読み込んだときの記録は古いことがある）
    except Exception:
        fresh = work.get("documents") or []
    docs = [{"kind": d["kind"], "title": d["title"],
             "count": (f"{d['articles']}{'項目' if d.get('style') == '項目' else 'か条'}" if d.get("articles") else "—")}
            for d in fresh] or None
    k = build(_corpus(work_id), docs)
    title = f"{_org(work)} 規約集の構成表".strip()
    return HTMLResponse(to_html(k, title, ident=_ident(work_id, work)))


@app.get("/works/{work_id}/taisho", response_class=HTMLResponse)
def taisho(work_id: str):
    p = store.path(work_id) / "taisho.html"
    if not p.exists():
        raise HTTPException(404, "新旧対照表はまだありません")
    # 開くたびに今の作りで書き直す（AI は使わない）。表の作りを直したとき、前に作った作業にも効くように（計画C）
    work = store.load(work_id)
    draft = _draft(work)
    if draft:
        try:
            _write_taisho(work_id, work, draft, _corpus(work_id))
        except Exception:   # 書き直せなくても、前に作った表は見せる
            pass
    return FileResponse(p, media_type="text/html; charset=utf-8")


DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _docx_response(data: bytes, ascii_name: str, name: str) -> Response:
    from urllib.parse import quote

    return Response(data, media_type=DOCX,
                    headers={"Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name)}"})


@app.get("/works/{work_id}/taisho.docx")
def taisho_docx(work_id: str):
    """新旧対照表を Word で（A4 横。委員会で直して、議案書に使えるように）。"""
    from core.wordout import taisho_docx as build

    work = store.load(work_id)
    draft = _draft(work)
    if not draft:
        raise HTTPException(404, "新旧対照表はまだありません")
    title = f"{_org(work)} 管理規約 新旧対照表（案）".strip()
    return _docx_response(build(draft, _corpus(work_id), title, ident=_ident(work_id, work), edits=work.get("human_edits"),
                                skipped=_skipped(work)),
                          "shinkyu_taisho.docx", f"{title}.docx")


@app.get("/works/{work_id}/board.docx")
def board_docx(work_id: str):
    """理事会の検討資料を Word で。"""
    from core.wordout import board_docx as build

    work = store.load(work_id)
    paper = _board(work)
    if not paper:
        raise HTTPException(404, "理事会の検討資料はまだありません")
    return _docx_response(build(paper, work.get("board_decisions") or None, _org(work), _points(work), ident=_ident(work_id, work)),
                          "rijikai_kentou.docx", f"{paper.title}.docx")


@app.get("/works/{work_id}/explain.docx")
def explain_docx(work_id: str):
    """住民向けの説明を Word で（理事会の判断を反映した改定案で、付録の一覧を作る）。"""
    from core.board import apply_to_draft
    from core.explain import Explanation
    from core.wordout import explain_docx as build

    work = store.load(work_id)
    draft, paper = _draft(work), _board(work)
    if not work.get("explain") or not draft:
        raise HTTPException(404, "住民向けの説明はまだありません")
    ex = Explanation.model_validate(work["explain"])
    shown = apply_to_draft(draft, paper, work.get("board_decisions", {})) if paper else draft
    return _docx_response(build(ex, _org(work), shown, ident=_ident(work_id, work)), "jumin_setsumei.docx", f"{ex.title}.docx")


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


def _apply_board_form(work_id: str, form) -> None:
    """理事会の判断を保存する（画面のフォーム、または写真の書き込みから組み立てた同じ形の値）。履歴も残す。"""
    from core.board import DECISIONS, NEEDS_REDRAFT
    from core.board import to_html as board_html

    work = store.load(work_id)
    paper = _board(work)
    if not paper:
        raise HTTPException(400, "検討資料がありません。")
    from core.history import record

    old = work.get("board_decisions", {})
    if not work.get("board_applied") and work.get("draft_reflects_board"):
        # 反映した判断の記録がない（この仕組みの前に作り直した）作業は、変える前の判断を反映済みとして記録する
        store.update(work_id, board_applied=_board_snapshot(old))
        work["board_applied"] = _board_snapshot(old)
    decisions = {}
    changed_redraft = False
    now = _now()
    from core.board import choice_questions, picked_text, point_key

    points = _points(work)
    from core.board import required_refs
    from core.explain import _ref_key

    draft_now = _draft(work)
    must = required_refs(draft_now) if draft_now else set()
    changed_any = False
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
        # 見送り ⇔ それ以外 を変えたとき、議題の条に法律で必須の変更も入っていれば、条の文を作り直す必要がある
        # （見送った部分を取り除く／採用に戻した部分を入れ直す。作り直したあとに変えても案内が出なかった、という声から）
        if (entry["decision"] == "見送り") != (prev.get("decision") == "見送り") and prev.get("decision") \
                and any(_ref_key(x) in must for x in it.articles):
            changed_redraft = True
        if entry["decision"] != prev.get("decision", "") or entry["choice"] != prev.get("choice", ""):
            changed_any = True
        if pts:
            entry["picked"] = picked
        entry["history"] = record(prev, entry["decision"], entry["note"], now, reason_key="note",
                                  extra={"choice": entry["choice"]})
        decisions[str(i)] = entry
    changes = {"board_decisions": decisions}
    if changed_redraft:
        changes["draft_reflects_board"] = False
    # 変えた判断を元に戻して、最後に作り直したときと同じになったら、作り直しは要らない（戻しただけで費用を求めない）
    if work.get("board_applied") and _board_snapshot(decisions) == work["board_applied"]:
        changes["draft_reflects_board"] = True
    # 総会の結果を記録したあとで判断を変えたら、印を付ける（最新の規約・住民向け説明と食い違うため。黙って書き換えない）
    # 説明・総会の結果を作ったときの判断に戻したら、判断のせいで付けた印は外す（戻しただけで作り直しや費用を求めない。想定ユーザーでの確認で分かった）
    snap = _board_snapshot(decisions)
    if any(((work.get("meeting") or {}).get("results") or {}).values()):
        if "meeting_board" in work and snap == work["meeting_board"]:
            if work.get("board_changed_reason") == "board":
                changes["board_changed_after_meeting"], changes["board_changed_reason"] = "", ""
        elif changed_any:
            changes["board_changed_after_meeting"] = now
            if not work.get("board_changed_after_meeting"):
                changes["board_changed_reason"] = "board"
    if work.get("explain"):
        if "explain_board" in work and snap == work["explain_board"]:
            if work.get("explain_stale_reason") == "board":
                changes["explain_stale"], changes["explain_stale_reason"] = False, ""
        elif changed_any:
            changes["explain_stale"] = True
            if not work.get("explain_stale"):
                changes["explain_stale_reason"] = "board"
    store.update(work_id, **changes)
    (store.path(work_id) / "board.html").write_text(board_html(paper, decisions, _org(work), points, ident=_ident(work_id, work)),
                                                    encoding="utf-8")
    work = store.load(work_id)
    if _draft(work):  # 見送りにした条の印を、新旧対照表にも付け直す
        _write_taisho(work_id, work, _draft(work), _corpus(work_id))


@app.post("/works/{work_id}/board/decisions")
async def save_board_decisions(request: Request, work_id: str):
    _apply_board_form(work_id, await request.form())
    return RedirectResponse(f"/works/{work_id}#board", status_code=303)


@app.post("/works/{work_id}/board/redraft")
def redraft_with_board(work_id: str, mode: str = Form("full")):
    """理事会の判断を改定案に反映する。mode=partial は対象の条だけ、それ以外は全体を最初から作り直す。"""
    work = store.load(work_id)
    if work["status"] in BUSY:
        raise HTTPException(409, "処理中です。終わるまでお待ちください。")
    if mode == "partial":
        if not redraft_targets(work)["amendments"]:
            raise HTTPException(400, "対象の条が見つかりませんでした。「全体を作り直す」を押してください。")
        store.update(work_id, status="改定案作成中", draft_with_board=True, draft_mode="partial")
        threading.Thread(target=_run_partial, args=(work_id,), daemon=True).start()
        return RedirectResponse(f"/works/{work_id}", status_code=303)
    store.update(work_id, status="改定案作成中", draft_with_board=True, draft_mode="full")
    threading.Thread(target=_run_draft, args=(work_id, True), daemon=True).start()
    return RedirectResponse(f"/works/{work_id}", status_code=303)


# ---- 理事会の判断を、対象の条だけに反映する（部分的な作り直し。core/partial.py） ----
# 全体の作り直しは 20〜45分・数ドルかかるため、〔選択〕を選んだだけ・メモで少し直すだけのときはこちらを勧める
PARTIAL_PLAN = {"estimate": "2〜5分", "cost": "数十セント"}


def _mark_after_meeting(data: dict) -> None:
    """総会の結果を記録したあとで改定案や判断が変わったら、印を付ける（最新の規約が知らせなく変わらないように）。
    住民向け説明を作ったあとなら、説明が古くなった印も付ける（ステップ5にも注意を出す）。"""
    if any(((data.get("meeting") or {}).get("results") or {}).values()):
        data["board_changed_after_meeting"] = _now()
        data["board_changed_reason"] = "other"   # 判断を戻しても外さない（条の文が変わったなど）
    if data.get("explain"):
        data["explain_stale"] = True
        data["explain_stale_reason"] = "other"


def _board_snapshot(decisions: dict) -> dict:
    """議題ごとの判断・メモ・選んだ案（作り直しで反映した時点のもの）。"""
    return {k: {"decision": d.get("decision", ""), "note": d.get("note", ""), "choice": d.get("choice", "")}
            for k, d in (decisions or {}).items()}


def redraft_targets(work: dict) -> dict:
    """部分的な作り直しの対象。見送りの議題は除く。

    「修正して採用」「要修正」の議題はその議題の条すべて、案を選んだだけの議題は〔選択〕のある条だけ。
    削除する条は書き直せないので対象にしない（削除をやめるなどは、全体の作り直しで）。
    """
    from core.board import NEEDS_REDRAFT
    from core.draft import CHOICE_MARK
    from core.explain import _ref_key, ref_name

    paper, draft = _board(work), _draft(work)
    if not paper or not draft:
        return {"items": [], "amendments": [], "refs": []}
    from core.board import required_refs

    decisions = work.get("board_decisions", {})
    by_key = {_ref_key(ref_name(a)): a for a in draft.amendments}
    must = required_refs(draft)
    applied = work.get("board_applied") or {}
    items, picked = [], []
    for i, it in enumerate(paper.items):
        d = decisions.get(str(i), {})
        if d.get("decision") in ("", None):
            continue
        # 前の作り直しで反映したときから判断・メモ・選んだ案が変わっていない議題は、対象にしない（反映済みをまた作り直さない）
        if applied.get(str(i)) == {"decision": d.get("decision", ""), "note": d.get("note", ""), "choice": d.get("choice", "")} \
                and not any(CHOICE_MARK in by_key[r].text for r in (_ref_key(x) for x in it.articles) if r in by_key):
            continue
        ams = [by_key[r] for r in (_ref_key(x) for x in it.articles) if r in by_key and by_key[r].kind != "削除"]
        # 最後に作り直したときに見送りだった議題を、採用などに戻したか（履歴ではなく、反映したときの記録と比べる）
        was_skipped = (applied.get(str(i)) or {}).get("decision") == "見送り"
        if d.get("decision") == "見送り":  # 必須の変更と同じ条に入っている部分だけ、作り直しで取り除く
            ams = [a for a in ams if _ref_key(ref_name(a)) in must]
        elif d.get("decision") not in NEEDS_REDRAFT:
            # 一度見送ったあとで採用に戻した議題は、必須と同じ条に入れ直す必要がある
            ams = [a for a in ams if CHOICE_MARK in a.text or a.choices or (was_skipped and _ref_key(ref_name(a)) in must)]
        if ams:
            items.append(it.title)
            picked += [a for a in ams if a not in picked]
    return {"items": items, "amendments": picked, "refs": [ref_name(a) for a in picked]}


def _run_partial(work_id: str) -> None:
    """対象の条だけを AI に書き直させ（1回）、別の呼び出しで確かめる（1回）。検査に通らなければ今の改定案のまま。"""
    from core import partial
    from core.board import decisions_text
    from core.draft import check as check_draft
    from core.explain import ref_name
    from core.present import basis
    from core.taisho import rows

    work = store.load(work_id)
    log = lambda k, t: store.append_log(work_id, k, t)
    usd = 0.0
    try:
        corpus, draft, paper = _corpus(work_id), _draft(work), _board(work)
        tg = redraft_targets(work)
        targets = tg["amendments"]
        log("writing", f"対象の条を読む：{'、'.join(tg['refs'])}")
        decisions = work.get("board_decisions", {})
        # 理事会の判断のうち、対象の議題のものだけを渡す
        sub = {str(i): d for i, d in decisions.items() if paper.items[int(i)].title in tg["items"]}
        board = decisions_text(paper, sub)
        olds = {(r["amendment"].document or "規約", r["amendment"].article): "".join(t for t, _ in r["old"])
                for r in rows(draft, corpus) if r["amendment"] in targets}
        human = work.get("human_edits") or {}
        tinfo = [{"amendment": a, "current": "" if a.kind == "新設" else olds.get((a.document or "規約", a.article), ""),
                  "basis": basis({"law_basis": a.law_basis, "standard_basis": a.standard_basis}),
                  "human_note": (human.get(f"{a.document or '規約'}|{a.article}") or {}).get("note") or
                                ("（補足なし）" if f"{a.document or '規約'}|{a.article}" in human else "")} for a in targets]
        refs_set = {x for a in targets for x in a.finding_refs} | {
            x for it in paper.items if it.title in tg["items"] for x in (it.finding_refs or [])}
        findings = [f for f in work.get("findings", []) if f.get("topic_id") in refs_set]
        others = partial.referencing(draft, targets)
        material = partial.write_material(targets=tinfo, board=board, findings=findings, others=others,
                                          all_refs=[ref_name(a) for a in draft.amendments], notes=draft.notes)
        log("builtin", "write：対象の条を書き直す")
        out, c1 = partial.rewrite(material)
        usd += c1
        new_draft, changed = partial.merge(draft, out, targets)
        adopted = [f for i, f in enumerate(_findings(work)) if work["decisions"][str(i)]["decision"] == "採用"]
        # 書き直しで新しく出たエラーだけで止める（作り直しと関係のない条に元からある注意で、毎回止めないため）
        _, errors_before, _ = check_draft(draft.to_dict(), corpus, adopted)
        checked, errors, _ = check_draft(new_draft.to_dict(), corpus, adopted)
        new_errors = [e for e in errors if e not in errors_before]
        if new_errors:
            raise ValueError("書き直した改定案が機械的な検査に通りませんでした：" + "／".join(new_errors[:3]))
        new_draft = checked or new_draft
        log("grading", "採点 直した条を確かめています")
        hnotes = {k: ("委員会で直した文。" + (f"補足：{e.get('note')}" if e.get("note") else "")) for k, e in human.items()}
        currents = {f"{t['amendment'].document or '規約'}|{t['amendment'].article}": t["current"] for t in tinfo}
        related = []
        for _, b in changed:
            related += _related(corpus, b.document or "規約", b.article, b.text, [o.ref for o in out.others])
        # 改定案にある条は、改定前ではなく改定案の文で確かめさせる（改定前の文と比べて誤った指摘が出た、という声から）
        amended = {re.sub(r"[\s　]", "", a.article): a for a in new_draft.amendments}
        for r in related:
            a = amended.get(re.sub(r"[\s　]", "", r["ref"]))
            if a is not None and a.kind != "削除":
                r["ref"], r["text"] = f"{r['ref']}（改定案の文）", a.text
        review, c2 = partial.check(partial.check_material(board=board, changed=changed, others=others, human_notes=hnotes,
                                                          currents=currents, related=related[:10]))
        usd += c2
        log("graded", f"直した条の確認：{review.verdict}")
        changed_refs = [ref_name(b) for _, b in changed]

        def save(data: dict) -> None:
            data["draft"] = new_draft.to_dict()
            # 委員会が手で直した条を書き直したときは、直した文を新しい文にする（作り直しのたびに古い文へ戻さないため）
            for _, b in changed:
                key = f"{b.document or '規約'}|{b.article}"
                e = (data.get("human_edits") or {}).get(key)
                if e is not None:
                    e["text"] = b.text
                    e["note"] = (e.get("note") or "") + "（理事会の判断を反映して AI が書き直しました）"
                    # 書き直した文は、確かめる役がこの場で確かめたので、その結果を条の印にも使う（「AI の確認前」のままにしない）
                    mine = [c.model_dump() for c in review.concerns if b.article in c.ref]
                    e["review"] = {"status": "済み", "for_text": b.text, "at": _now(), "cost_usd": 0,
                                   "verdict": "問題なし" if not mine else ("法律に合わないおそれ" if any(c["kind"] == "法律に合わないおそれ" for c in mine) else "気になる点あり"),
                                   "summary": "理事会の判断を反映して書き直したときに、AI が確かめました。",
                                   "concerns": [{"kind": c["kind"] if c["kind"] in ("法律に合わないおそれ", "他の条と食い違う", "要確認") else "要確認",
                                                 "point": c["point"], "basis": c["basis"], "suggestion": c["suggestion"]} for c in mine]}
            data["status_since"] = __import__("time").time()
            data["board_applied"] = _board_snapshot(data.get("board_decisions", {}))  # 反映した判断（次の作り直しの対象から外すため）
            _mark_after_meeting(data)
            # 説明まで済んでいる作業は、状態を「改定案あり」に戻さない（一覧で前の段階に戻ったように見えた）
            later = "説明文あり" if data.get("explain") else ("検討資料あり" if data.get("board") else "改定案あり")
            data.update(status=later, draft_reflects_board=True, draft_stale=False, draft_mode="partial",
                        interrupted="", interrupted_session="",
                        draft_partial={"status": "済み", "at": _now(), "targets": tg["refs"], "changed": changed_refs,
                                       "summary": out.summary, "others": [o.model_dump() for o in out.others],
                                       "check": review.model_dump(), "cost_usd": round(usd, 4), "checked_with": "related_v2"})
            data.setdefault("costs", []).append(_cost_entry(f"改定案の部分的な作り直し（{'、'.join(tg['refs'])}）",
                                                            {"amount": max(1, round(usd * 100)), "currency": "USD"}))
        store.mutate(work_id, save)
        work = store.load(work_id)
        _write_taisho(work_id, work, _draft(work), corpus)
        log("edit", f"理事会の判断を反映して、{'、'.join(changed_refs) or '対象の条'}を書き直しました（約${usd:.2f}）")
    except Exception as e:
        log("error", f"{type(e).__name__}: {e}")
        msg = f"{type(e).__name__}: {e}"[:400]

        def fail(data: dict) -> None:  # 今の改定案はそのまま残っているので、改定案はある状態に戻す
            data["status_since"] = __import__("time").time()
            data.update(status=("説明文あり" if data.get("explain") else "検討資料あり" if data.get("board") else "改定案あり")
                        if data.get("draft") else "改定案エラー", draft_mode="partial",
                        draft_partial={"status": "失敗", "at": _now(), "error": msg,
                                       "cost_usd": round(usd, 4)})
            if usd:
                data.setdefault("costs", []).append(_cost_entry("改定案の部分的な作り直し（失敗）",
                                                                {"amount": max(1, round(usd * 100)), "currency": "USD"}))
        store.mutate(work_id, fail)


@app.get("/works/{work_id}/board", response_class=HTMLResponse)
def board_page(work_id: str):
    p = store.path(work_id) / "board.html"
    if not p.exists():
        raise HTTPException(404, "理事会の検討資料はまだありません")
    return FileResponse(p, media_type="text/html; charset=utf-8")


# ---- 書き込みの反映：委員会・理事会で印刷した資料に書き込んだ内容を、スマホの写真から読み取って反映する ----
# 流れ：写真を読み込む → AI が書き込みを読み取る（写真1枚ずつ、終わるたびに保存）→ 提案 → 人が確かめて反映（AI は使わない）
NOTE_DOCS = {"taisho": "新旧対照表", "board": "理事会の検討資料"}


def _note_batch(work: dict, batch: str) -> dict:
    for b in work.get("notes", []):
        if b["id"] == batch:
            return b
    raise HTTPException(404, "書き込みの読み込みが見つかりません")


def _notes_dir(work_id: str, batch: str) -> Path:
    if not batch.replace("-", "").isalnum():
        raise HTTPException(404, "書き込みの読み込みが見つかりません")
    return store.path(work_id) / "notes" / batch


def _with_batch(work_id: str, batch: str, fn) -> None:
    def change(data: dict) -> None:
        for b in data.get("notes", []):
            if b["id"] == batch:
                fn(b)
    store.mutate(work_id, change)


@app.post("/works/{work_id}/notes")
async def upload_notes(work_id: str, doc: str = Form(...), photos: list[UploadFile] = File(...)):
    """書き込みのある資料の写真を読み込み、読み取りを始める（写真は何枚でも）。"""
    from core.notes import preprocess

    work = store.load(work_id)
    if doc not in NOTE_DOCS:
        raise HTTPException(400, "資料の種類が正しくありません")
    if (doc == "taisho" and not work.get("draft")) or (doc == "board" and not work.get("board")):
        raise HTTPException(400, f"{NOTE_DOCS[doc]}がまだありません。")
    batch = __import__("datetime").datetime.now().strftime("%Y%m%d%H%M%S")
    d = _notes_dir(work_id, batch)
    d.mkdir(parents=True, exist_ok=True)
    saved, skipped = [], 0
    for f in photos:
        try:
            jpeg = preprocess(await f.read())
        except ValueError:
            skipped += 1
            continue
        n = len(saved) + 1
        (d / f"p{n}.jpg").write_bytes(jpeg)  # 開き直した画像だけを保存する（元のファイルは保存しない）
        saved.append({"n": n, "status": "待ち"})
    if not saved:
        raise HTTPException(400, "写真を読み込めませんでした。スマホで撮った写真（JPEG・PNG など）を選んでください。")
    entry = {"id": batch, "at": _now(), "doc": doc, "status": "読み取り中", "photos": saved, "proposals": [],
             "ident": _ident(work_id, work), "cost_usd": 0.0, "skipped": skipped}
    store.mutate(work_id, lambda data: data.setdefault("notes", []).append(entry))
    threading.Thread(target=_read_notes, args=(work_id, batch), daemon=True).start()
    return RedirectResponse(f"/works/{work_id}/notes/{batch}", status_code=303)


def _read_notes(work_id: str, batch: str) -> None:
    """写真を1枚ずつ読み取り、終わるたびに保存する（途中で止まっても、読み取った分は残る）。"""
    from core.notes import (
        board_context,
        build_proposals,
        cost_usd,
        read_photo,
        taisho_context,
    )

    work = store.load(work_id)
    b = _note_batch(work, batch)
    draft, paper = _draft(work), _board(work)
    corpus = _corpus(work_id) if draft else None
    points = _points(work)
    context = taisho_context(draft, corpus) if b["doc"] == "taisho" else board_context(paper, points)
    for ph in b["photos"]:
        if ph["status"] == "読み取り済み":
            continue
        n = ph["n"]
        try:
            reading, usage = read_photo((_notes_dir(work_id, batch) / f"p{n}.jpg").read_bytes(), context)
            props = build_proposals(reading, n, draft=draft, corpus=corpus, paper=paper, points=points,
                                    board_decisions=work.get("board_decisions", {}))

            def done(bb, n=n, reading=reading, usage=usage, props=props):
                for p in bb["photos"]:
                    if p["n"] == n:
                        p.update(status="読み取り済み", document=reading.document, ident=reading.ident, page=reading.page,
                                 note=reading.note, cost_usd=cost_usd(usage), usage=usage)
                bb["proposals"] = [p for p in bb["proposals"] if p["photo"] != n] + props
                bb["cost_usd"] = round(sum(p.get("cost_usd", 0) for p in bb["photos"]), 4)
            _with_batch(work_id, batch, done)
        except Exception as e:  # 1枚読めなくても、残りの写真は読み取る
            store.append_log(work_id, "error", f"写真{n}を読み取れませんでした：{type(e).__name__}")

            def failed(bb, n=n, e=e):
                for p in bb["photos"]:
                    if p["n"] == n:
                        p.update(status="失敗", error=f"{type(e).__name__}: {e}"[:300])
            _with_batch(work_id, batch, failed)
    _with_batch(work_id, batch, lambda bb: bb.update(status="読み取り済み"))


@app.post("/works/{work_id}/notes/{batch}/resume")
def resume_notes(work_id: str, batch: str):
    """途中で止まった読み取りを、残りの写真から続ける。"""
    b = _note_batch(store.load(work_id), batch)
    if b["status"] == "読み取り中":
        raise HTTPException(409, "読み取り中です。終わるまでお待ちください。")
    _with_batch(work_id, batch, lambda bb: bb.update(status="読み取り中"))
    threading.Thread(target=_read_notes, args=(work_id, batch), daemon=True).start()
    return RedirectResponse(f"/works/{work_id}/notes/{batch}", status_code=303)


@app.get("/works/{work_id}/notes/{batch}/status")
def notes_status(work_id: str, batch: str):
    """写真の読み取りの進み具合（画面が3秒ごとに聞き、写真が1枚読めるたびに画面を切り替える）。"""
    b = _note_batch(store.load(work_id), batch)
    done = sum(1 for p in b["photos"] if p["status"] in ("読み取り済み", "失敗"))
    return JSONResponse({"status": b["status"], "done": done})


@app.get("/works/{work_id}/notes/{batch}/photo/{n}")
def note_photo(work_id: str, batch: str, n: int):
    p = _notes_dir(work_id, batch) / f"p{int(n)}.jpg"
    if not p.exists():
        raise HTTPException(404, "写真が見つかりません")
    return FileResponse(p, media_type="image/jpeg")


@app.get("/works/{work_id}/notes/{batch}", response_class=HTMLResponse)
def notes_page(request: Request, work_id: str, batch: str):
    """読み取った書き込みと、反映の提案を確かめる画面。"""
    from core.board import DECISIONS
    from core.notes import changes

    work = store.load(work_id)
    b = _note_batch(work, batch)
    if b["doc"] == "board":  # 写真にない内容を足すときの「場所」
        paper = _board(work)
        places = [(f"item:{i}", f"議題{i + 1} {it.title}") for i, it in enumerate(paper.items)] if paper else []
    else:
        places = list(_row_labels(work_id, work).items())
    return templates.TemplateResponse(request, "notes.html", {
        "id": work_id, "work": work, "b": b, "doc_name": NOTE_DOCS[b["doc"]], "ident_now": _ident(work_id, work),
        "changes": changes, "places": places,
        "decision_options": list(dict.fromkeys(d for ds in DECISIONS.values() for d in ds)),
        "done": request.query_params.get("done", ""), "texts": request.query_params.get("texts", ""),
    })


@app.post("/works/{work_id}/notes/{batch}/apply")
async def apply_notes(request: Request, work_id: str, batch: str):
    """選んだ提案を反映する（AI は使わない）。条の文の修正は、あとで改定案を作り直しても上書きしない。

    提案ごとの「補足」（会議での経緯など）と、写真にない内容を手で足した分も、ここで一緒に記録する。
    """
    from core.board import choice_questions

    form = await request.form()
    work = store.load(work_id)
    b = _note_batch(work, batch)
    now = _now()
    chosen = []
    for p in b["proposals"]:
        if p["status"] != "未確認":
            continue
        act = str(form.get(f"act_{p['id']}", ""))
        if act not in ("反映する", "反映しない"):
            continue
        text = str(form.get(f"text_{p['id']}", p.get("proposed", ""))).strip()
        if act == "反映する" and not text:  # 中身のない提案（文字を入れていない「読めない」など）は、反映済みにせず残す
            continue
        chosen.append((p, act, text))
    memos = {p["id"]: str(form.get(f"memo_{p['id']}", "")).strip() for p, _, _ in chosen}
    added = _manual_proposals(work_id, work, b, form)  # 写真にない内容を手で足した分は、そのまま反映する
    for p in added:
        chosen.append((p, "反映する", p["proposed"]))
        memos[p["id"]] = p.get("memo", "")
    applied = [(p, t) for p, act, t in chosen if act == "反映する" and t]
    applied_text = {p["id"]: t for p, t in applied}
    stamp = f"{now} の書き込みから"

    # 条の文の修正：改定案を直し、委員会で直した文として記録する（AI の元の文も残す）
    edits = [{"document": p.get("document", "規約"), "article": p["article"], "text": t, "note": memos.get(p["id"], "")}
             for p, t in applied if p["kind"] == "文言の修正"]
    if edits:
        _edit_articles(work_id, edits, f"{stamp}：条の文を直しました", batch=batch)

    # 理事会の判断・〔選択〕・メモ：画面のフォームと同じ形にして、同じ処理で保存する（履歴も残る）
    board_props = [(p, t) for p, t in applied if p["kind"] in ("判断", "選択", "理事会のメモ")]
    if board_props:
        work = store.load(work_id)
        paper = _board(work)
        form_now = {}
        dec = work.get("board_decisions", {})
        for i, _ in enumerate(paper.items):
            d = dec.get(str(i), {})
            form_now[f"b_decision_{i}"] = d.get("decision", "")
            form_now[f"b_note_{i}"] = d.get("note", "")
        qs = choice_questions(_points(work))
        for k, ans in enumerate(_questions_context(work)["answers"]):
            form_now[f"b_q_{k}"] = ans

        def add_note(i: int, text: str) -> None:
            old = form_now[f"b_note_{i}"]
            form_now[f"b_note_{i}"] = f"{old}／{text}" if old else text

        for p, t in board_props:
            i = p["item"]
            if p["kind"] == "判断":
                form_now[f"b_decision_{i}"] = t
            elif p["kind"] == "理事会のメモ":
                add_note(i, t)
            else:
                k = next((k for k, q in enumerate(qs) if (i, p["point"]) in q["uses"]), None)
                if k is not None:
                    form_now[f"b_q_{k}"] = t
            if memos.get(p["id"]):  # 補足（会議での経緯）は、議題のメモに残す（議事録に使える）
                add_note(i, memos[p["id"]])
        _apply_board_form(work_id, form_now)
        store.append_log(work_id, "edit", f"{stamp}：理事会の判断などを記録しました（{len(board_props)}件）")

    # メモ・宿題（読めなかった書き込みに、人が文字を入れた場合も）
    todos = [{"id": _todo_id(), "text": t, "where": p["where"], "at": now, "batch": batch, "memo": memos.get(p["id"], ""),
              "done": False}
             for p, t in applied if p["kind"] in ("メモ・宿題", "読めない")]
    ids = {p["id"]: act for p, act, _ in chosen}

    def finish(data: dict) -> None:
        if todos:
            data.setdefault("todos", []).extend(todos)
        for bb in data.get("notes", []):
            if bb["id"] == batch:
                bb["proposals"].extend(added)
                for p in bb["proposals"]:
                    if p["id"] in ids:
                        p.update(status="反映済み" if ids[p["id"]] == "反映する" else "反映しない", decided_at=now)
                        if p["id"] in applied_text:  # 実際に反映した文（人が直したあとの文）を残す。カードに AI の元の案を出さないため
                            p["applied_text"] = applied_text[p["id"]]
                        if memos.get(p["id"]):
                            p["memo"] = memos[p["id"]]
    store.mutate(work_id, finish)
    texts = any(p["kind"] == "文言の修正" for p, _ in applied)  # 文を直したら、変更の理由も確かめるよう促す
    return RedirectResponse(f"/works/{work_id}/notes/{batch}?done={len(applied)}{'&texts=1' if texts else ''}", status_code=303)


def _manual_proposals(work_id: str, work: dict, b: dict, form) -> list[dict]:
    """確認画面で、写真にない内容を手で足した分を、提案と同じ形にする（会議のあとで思い出して足す場合など）。

    場所は「全体」「行N（新旧対照表）」「議題N（検討資料）」。議題の判断は、その議題で選べるものだけを記録し、
    選べないものはメモにする（写真の読み取りと同じ扱い）。条の文を直すときは「条の文を直す」画面を使う。
    """
    from core.board import DECISIONS

    text = str(form.get("add_text", "")).strip()
    decision = str(form.get("add_decision", "")).strip()
    place = str(form.get("add_place", "")).strip()
    memo = str(form.get("add_memo", "")).strip()
    if not text and not decision:
        return []
    n = sum(1 for p in b["proposals"] if p["photo"] == 0)
    out = []

    def add(kind: str, where: str, proposed: str, **kw) -> None:
        out.append({"kind": kind, "photo": 0, "id": f"0-{n + len(out) + 1}", "where": where, "handwriting": "",
                    "confidence": "", "reason": "", "check": False, "status": "未確認", "manual": True,
                    "proposed": proposed, **kw})

    paper = _board(work)
    if place.startswith("item:") and paper and place[5:].isdigit() and int(place[5:]) < len(paper.items):
        i = int(place[5:])
        it = paper.items[i]
        where = f"議題{i + 1} {it.title}"
        d = work.get("board_decisions", {}).get(str(i), {})
        if decision in DECISIONS[it.tier]:
            add("判断", where, decision, item=i, current=d.get("decision", ""))
        elif decision:
            text = f"☑{decision}" + (f"／{text}" if text else "")
        if text:
            add("理事会のメモ", where, text, item=i, current=d.get("note", ""))
    else:
        where = "全体"
        if place.startswith("row:"):
            where = _row_labels(work_id, work).get(place, "全体")
        body = "／".join(x for x in (f"☑{decision}" if decision else "", text) if x)
        add("メモ・宿題", where, body)
    if out:
        out[0]["memo"] = memo
    return out


def _row_labels(work_id: str, work: dict) -> dict[str, str]:
    """新旧対照表の行の番号と見出し（例：{"row:2": "行2 第25条の2（保険金等の請求及び受領等）"}）。"""
    from core.taisho import numbered, rows

    draft = _draft(work)
    if not draft:
        return {}
    return {f"row:{n}": f"行{n} {r['amendment'].article}（{r['amendment'].caption}）"
            for _doc, items in numbered(rows(draft, _corpus(work_id))) for n, r in items}


def _todo_id() -> str:
    import uuid

    return uuid.uuid4().hex[:8]


def _keep_human_edits(work: dict, draft) -> list[str]:
    """改定案を作り直したとき、委員会の書き込みで直した条の文と、人が書き直した理由を引き継ぐ（AI の新しい文で黙って上書きしない）。"""
    kept = []
    for key, e in (work.get("human_reasons") or {}).items():
        document, article = key.split("|", 1)
        for am in draft.amendments:
            if am.article == article and (am.document or "規約") == document and am.reason != e["reason"]:
                am.reason = e["reason"]
    for key, e in (work.get("human_edits") or {}).items():
        document, article = key.split("|", 1)
        for am in draft.amendments:
            if am.article == article and (am.document or "規約") == document and am.text != e["text"]:
                am.text = e["text"]
                kept.append(article)
    return kept


def _edit_articles(work_id: str, edits: list[dict], log: str, batch: str = "") -> None:
    """人が直した条の文を改定案に入れ、委員会で直した文として記録する（AI の元の文も残す。AI は使わない）。

    edits の各要素：{"document", "article", "text", "note"}。text が None なら、AI が作った文に戻す。
    直した文は、あとで改定案を作り直しても上書きしない（_keep_human_edits）。
    """
    from core.draft import check

    now = _now()

    def change(data: dict) -> None:
        human = data.setdefault("human_edits", {})
        for e in edits:
            key = f"{e['document']}|{e['article']}"
            if e.get("text"):  # 改行の形をそろえる（写真の反映などで \r\n が混じり、変わらない行が差分に出た）
                e["text"] = e["text"].replace("\r\n", "\n").replace("\r", "\n")
            for am in data["draft"]["amendments"]:
                if am["article"] != e["article"] or am.get("document", "規約") != e["document"]:
                    continue
                if e["text"] is None:  # AI の文に戻す
                    if key in human:
                        am["text"] = human.pop(key)["original"]
                    continue
                prev = human.get(key, {})
                note = e.get("note", "")
                # 写真の書き込みから反映したときは、前の補足（委員会の経緯）を消さずに書き足す（上書きで経緯が消えた、という声から）
                if batch and prev.get("note") and note and note not in prev["note"]:
                    note = f"{prev['note']}\n{now}：{note}"
                elif batch and prev.get("note") and not note:
                    note = prev["note"]
                human[key] = {"text": e["text"], "original": prev.get("original", am["text"]), "at": now,
                              "batch": batch, "note": note}
                _mark_after_meeting(data)
                if prev.get("review") and prev.get("text") == e["text"]:  # 補足だけ直したときは、AI の確認の結果を残す
                    human[key]["review"] = prev["review"]
                am["text"] = e["text"]
    work = store.mutate(work_id, change)
    draft = _draft(work)
    corpus = _corpus(work_id)
    _, errors, _ = check(draft.to_dict(), corpus, [f for i, f in enumerate(_findings(work))
                                                   if work["decisions"][str(i)]["decision"] == "採用"])
    store.update(work_id, draft_errors=errors)
    _write_taisho(work_id, work, draft, corpus)
    _rerender(work_id)
    store.append_log(work_id, "edit", f"{log}（{'、'.join(e['article'] for e in edits)}）")


@app.get("/works/{work_id}/articles", response_class=HTMLResponse)
def articles_page(request: Request, work_id: str):
    """改定案の条の文を、人が直接直す画面（委員会のあとで見返して直す場合など）。"""
    from core.taisho import numbered, rows

    work = _unstick_reviews(work_id, store.load(work_id))
    draft = _draft(work)
    if not draft:
        raise HTTPException(404, "改定案がまだありません。")
    human = work.get("human_edits") or {}
    items = []
    for document, group in numbered(rows(draft, _corpus(work_id))):
        for n, r in group:
            am = r["amendment"]
            # 削除する条も一覧に出す（細則の削除などが見当たらない、という声から）。文は直せないので、見るだけ
            items.append({"n": n, "document": document, "article": am.article, "caption": am.caption, "kind": am.kind,
                          "current": "".join(t for t, _ in r["old"]), "text": am.text, "reason": am.reason,
                          "reason_edit": (work.get("human_reasons") or {}).get(f"{am.document}|{am.article}"),
                          "edit": human.get(f"{am.document}|{am.article}")})
    from core.editcheck import label

    for it in items:
        it["label"] = label(it["edit"], it["text"]) if it["edit"] else ""
    return templates.TemplateResponse(request, "articles.html", {
        "id": work_id, "work": work, "items": items, "ident": _ident(work_id, work), "counts": edit_counts(work),
        "reviewing": any((e.get("review") or {}).get("status") == "確認中" for e in human.values()),
        "review_progress": _review_progress(human),
        "busy": work["status"] in BUSY, "saved": request.query_params.get("saved", ""),
        "reverted": request.query_params.get("reverted", ""),
    })


@app.post("/works/{work_id}/articles")
async def save_articles(request: Request, work_id: str):
    """条の文の手直しを保存する。開いたあとに改定案が変わっていたら、上書きせずに開き直してもらう。"""
    form = await request.form()
    work = store.load(work_id)
    if work["status"] in BUSY:
        raise HTTPException(409, "AI が作業中です。終わってから直してください。")
    if str(form.get("ident", "")) != _ident(work_id, work):
        raise HTTPException(409, "この画面を開いたあとに、改定案が変わりました。画面を開き直してから、もう一度直してください。")
    human = work.get("human_edits") or {}
    edits, reasons = [], []
    for am in _draft(work).amendments:
        key = f"{am.document}|{am.article}"
        reason = form.get(f"reason_{key}")
        if reason is not None:  # 変更の理由も直せる（委員会で直した文に合わせて、人が書き換える）
            reason = str(reason).replace("\r\n", "\n").replace("\r", "\n").strip()
            if reason != am.reason.replace("\r\n", "\n").strip():
                reasons.append({"document": am.document, "article": am.article, "reason": reason})
        if am.kind == "削除":
            continue
        if form.get(f"revert_{key}") and key in human:
            edits.append({"document": am.document, "article": am.article, "text": None})
            continue
        # 改行の形（ブラウザは \r\n で送る）をそろえてから比べる。そろえないと、直していない条まで「直した」扱いになる
        nl = lambda x: str(x or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        text = nl(form.get(f"text_{key}", am.text))
        note = nl(form.get(f"note_{key}", ""))
        if not text:
            continue
        if text != nl(am.text) or (key in human and note != nl(human[key].get("note", ""))):
            edits.append({"document": am.document, "article": am.article, "text": text, "note": note})
    if reasons:
        _edit_reasons(work_id, reasons)
    if edits:
        _edit_articles(work_id, edits, f"{_now()} 条の文を直しました")
    elif reasons:
        work = store.load(work_id)
        _write_taisho(work_id, work, _draft(work), _corpus(work_id))
        _rerender(work_id)
    n = len({(e["document"], e["article"]) for e in edits + reasons})  # 文と理由を直した同じ条は1条と数える
    return RedirectResponse(f"/works/{work_id}/articles?saved={n}", status_code=303)


def _edit_reasons(work_id: str, reasons: list[dict]) -> None:
    """人が書き直した変更の理由を改定案に入れる。AI の元の理由は残し、空にすると AI の理由に戻す。

    条の文の手直し（human_edits）とは別に記録する（理由だけ直した条に「委員会で直した文」の印を付けないため）。
    改定案を作り直しても残す（_keep_human_edits）。
    """
    now = _now()

    def change(data: dict) -> None:
        hr = data.setdefault("human_reasons", {})
        for e in reasons:
            key = f"{e['document']}|{e['article']}"
            for am in data["draft"]["amendments"]:
                if am["article"] != e["article"] or am.get("document", "規約") != e["document"]:
                    continue
                original = hr.get(key, {}).get("original", am["reason"])
                if not e["reason"] or e["reason"] == original:  # 空なら AI の理由に戻す
                    am["reason"] = original
                    hr.pop(key, None)
                else:
                    am["reason"] = e["reason"]
                    hr[key] = {"reason": e["reason"], "original": original, "at": now}
                _mark_after_meeting(data)
    store.mutate(work_id, change)
    store.append_log(work_id, "edit", f"{_now()} 変更の理由を直しました（{'、'.join(e['article'] for e in reasons)}）")


@app.post("/works/{work_id}/articles/revert")
async def revert_article(request: Request, work_id: str):
    """委員会で直した条を、AI が作った文に戻す（ボタン1つで。AI は使わない）。"""
    form = await request.form()
    work = store.load(work_id)
    if work["status"] in BUSY:
        raise HTTPException(409, "AI が作業中です。終わってから戻してください。")
    if str(form.get("ident", "")) != _ident(work_id, work):
        raise HTTPException(409, "この画面を開いたあとに、改定案が変わりました。画面を開き直してから、もう一度押してください。")
    key = str(form.get("key", ""))
    if key not in (work.get("human_edits") or {}):
        raise HTTPException(400, "戻す条が見つかりません。画面を開き直してください。")
    document, article = key.split("|", 1)
    _edit_articles(work_id, [{"document": document, "article": article, "text": None}], f"{_now()} AI が作った文に戻しました")
    return RedirectResponse(f"/works/{work_id}/articles?reverted={article}", status_code=303)


@app.post("/works/{work_id}/todos")
async def save_todos(request: Request, work_id: str):
    """書き込みから残した宿題・メモを、直す・済みにする・消す・足す（AI は使わない）。"""
    form = await request.form()
    back = "#board" if form.get("back") == "board" else "#next"
    now = _now()

    def change(data: dict) -> None:
        keep = []
        for i, t in enumerate(data.get("todos", [])):
            tid = t.setdefault("id", f"i{i}")
            if f"text_{tid}" not in form:  # 画面に出ていなかった宿題（別の画面で足された分）は、そのまま残す
                keep.append(t)
                continue
            if form.get(f"del_{tid}"):
                continue
            text = str(form.get(f"text_{tid}", "")).strip()
            memo = str(form.get(f"memo_{tid}", "")).strip()
            done = bool(form.get(f"done_{tid}"))
            if text and (text, memo, done) != (t.get("text"), t.get("memo", ""), t.get("done", False)):
                t.update(text=text, memo=memo, done=done, edited_at=now)
            keep.append(t)
        new = str(form.get("new_text", "")).strip()
        if new:
            keep.append({"id": _todo_id(), "text": new, "where": str(form.get("new_where", "")).strip() or "全体",
                         "at": now, "batch": "", "memo": "", "done": False})
        data["todos"] = keep
    store.mutate(work_id, change)
    return RedirectResponse(f"/works/{work_id}{back}", status_code=303)



def edit_counts(work: dict) -> dict:
    """委員会で直した条の数と、AI の確認前の条（直したあとに確かめていないものも含む）、AI が気になる点を挙げた条。"""
    from core.editcheck import label

    edits = work.get("human_edits") or {}
    unchecked = [k.split("|", 1)[1] for k, e in edits.items() if "確認前" in label(e)]
    flagged = [f"{k.split('|', 1)[1]}（{e['review']['verdict']}）" for k, e in edits.items()
               if "確認済み" in label(e) and e["review"].get("verdict") != "問題なし"]
    return {"total": len(edits), "unchecked": unchecked, "flagged": flagged}


templates.env.globals["edit_counts"] = edit_counts


def board_preview(work: dict) -> dict:
    """理事会の検討資料を作る前の見込み：改定する条のうち、法律の改正に合わせる変更（①に入る）とそれ以外（②か③）、〔選択〕のある条。"""
    from core.topics import REQUIRED_TOPIC_IDS

    ams = (work.get("draft") or {}).get("amendments", [])
    req = sum(1 for a in ams if set(a.get("finding_refs") or []) & set(REQUIRED_TOPIC_IDS))
    return {"total": len(ams), "required": req, "other": len(ams) - req,
            "choices": sum(1 for a in ams if a.get("choices"))}


templates.env.globals["board_preview"] = board_preview
templates.env.globals["current_variants"] = current_variants
templates.env.globals["variant_view"] = variant_view


def draft_side_notes(work: dict) -> list[str]:
    """改定案の申し送りの「あわせて検討するとよい点」（指摘の範囲外で AI が気づいた点。例：ほかの法律の古い条番号）を1点ずつ。
    新旧対照表の最後にしか出ず、見落とされていた（想定ユーザーでの確認から）。"""
    from core.taisho import notes_sections

    notes = ((work.get("draft") or {}).get("notes") or "")
    for head, body in notes_sections(notes):
        if "あわせて検討" in head:
            lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
            items = [ln.lstrip("・").strip() for ln in lines if ln.startswith("・")]
            return items or lines                # 「・」の箇条書きがあればそれだけ（見出しのあとの補足は数えない）
    return []


templates.env.globals["draft_side_notes"] = draft_side_notes


def draft_blanks(work: dict) -> list[dict]:
    """改定案の条に残る「○」の空欄（標準管理規約で組合が数字を入れる箇所。計画D1）。"""
    from core.blanks import in_draft

    return in_draft(work.get("draft"))


def blank_slots(raw: list[dict], fills: dict, org: str) -> list[dict]:
    """ステップ6の入力欄：別表のような表は除き、入れた数字と、マンション名の初めの値（作業に入れたマンション名）を添える。"""
    from core.blanks import is_table

    name = re.sub(r"(?:マンション)?(?:管理組合)?$", "", org.strip()) if org else ""   # 「○○マンション」の○○に入れるので、後ろの「マンション管理組合」を外す
    out = []
    for x in raw:
        if is_table(x):
            continue
        vals = fills.get(x["where"]) or []
        slots = [dict(s, value=vals[s["i"]] if s["i"] < len(vals) else "",
                      suggest=name if name and s["after"].startswith("マンション") else "") for s in x["slots"]]
        out.append(dict(x, slots=slots))
    return out


def blanks_in(blocks) -> list[dict]:
    from core.blanks import in_blocks

    return in_blocks(blocks)


templates.env.globals["draft_blanks"] = draft_blanks
templates.env.globals["blank_view"] = blank_view
templates.env.globals["name_topics"] = lambda t: __import__("core.topics", fromlist=["name_topics"]).name_topics(t)
def ai_note(kind: str, work: dict) -> str:
    """AI を動かすボタンを押したときの確認の文（何をするか・時間・費用の目安）。費用は APIキーの持ち主に請求される。"""
    from core.progress import draft_plan

    plan = draft_plan(_adopted_count(work))
    tail = "\n費用は、このツールに登録した AI の利用料（APIキー）として請求されます（$1 は約150円）。画面を閉じても処理は続きます。始めますか？"
    notes = {
        "draft": f"改定案を作ります（AI が動きます）。\n改定案に入れる指摘 {plan['adopted']}件：目安 {plan['estimate']}・AI の費用 {plan['cost']}ほど。",
        "redraft": f"改定案を最初から全部作り直します（AI が動きます）。\n目安 {plan['estimate']}・AI の費用 {plan['cost']}ほど。委員会で直した文は残ります。",
        "resume": "止まったところから続けます（AI が動きます）。最初から作り直すより費用を抑えられます。",
        "partial": f"対象の条（{'、'.join(redraft_targets(work)['refs'])}）だけを作り直します（AI が動きます）。\n目安 {PARTIAL_PLAN['estimate']}・AI の費用 {PARTIAL_PLAN['cost']}ほど。",
        "board": "理事会の検討資料を作ります（AI が動きます）。\n目安 1〜2分・AI の費用 数十セントほど。",
        "board_redo": "理事会の検討資料を作り直します（AI が動きます）。\n入れた理事会の判断はリセットされます。目安 1〜2分・AI の費用 数十セントほど。",
        "explain": ("住民向けの説明を作り直します（AI が動きます）。" if work.get("explain") else "住民向けの説明を作ります（AI が動きます）。")
                   + "\n目安 1〜2分・AI の費用 数十セントほど。",
    }
    return notes[kind] + tail


templates.env.globals["ai_note"] = ai_note
templates.env.globals["display_status"] = store.display_status
templates.env.globals["cost_total"] = lambda work: __import__("core.quality", fromlist=["cost_lines"]).cost_lines(work)["total"]
templates.env.globals["draft_plan_for"] = lambda work: __import__("core.progress", fromlist=["draft_plan"]).draft_plan(_adopted_count(work))
templates.env.globals["redraft_targets"] = redraft_targets
templates.env.globals["partial_plan"] = PARTIAL_PLAN


def _review_material(work_id: str, work: dict, key: str) -> str:
    from core.editcheck import context
    from core.present import basis
    from core.taisho import rows

    document, article = key.split("|", 1)
    e = work["human_edits"][key]
    draft = _draft(work)
    am, row = next(((r["amendment"], r) for r in rows(draft, _corpus(work_id))
                    if r["amendment"].article == article and (r["amendment"].document or "規約") == document), (None, None))
    if am is None:
        raise ValueError(f"{article} が改定案にありません")
    current = "" if am.kind == "新設" else "".join(t for t, _ in row["old"])
    findings = [f for f in work.get("findings", []) if f.get("document", "規約") == document
                and (f.get("article") in (am.article, am.before_article) or f.get("topic_id") in am.finding_refs)]
    return context(article=article, caption=am.caption, current=current, original=e["original"], edited=e["text"],
                   note=e.get("note", ""), findings=findings,
                   basis=basis({"law_basis": am.law_basis, "standard_basis": am.standard_basis})
                   + _definitions(_corpus(work_id), e["original"] + e["text"])
                   + _related(_corpus(work_id), document, article, e["original"] + e["text"]))


def _related(corpus, document: str, article: str, text: str, extra: list[str] | None = None) -> list[dict]:
    """確かめる役に渡す、関係する条の今の文：文中で参照している条・枝番のもとの条（第38条の2 → 第38条）・extra に挙げた条。

    渡していない条について「資料からは分からない」と人に確認を頼ませないため（想定ユーザーでの確認で分かった）。
    """
    from core.sources import normalize_article_ref

    refs = re.findall(r"第[0-9０-９一二三四五六七八九十百]+条(?:の[0-9０-９一二三四五六七八九十]+)?", text) + list(extra or [])
    base = re.match(r"(第[0-9０-９一二三四五六七八九十百]+条)の", article)
    if base:
        refs.append(base.group(1))
    out, seen = [], {normalize_article_ref(article)}
    for r in refs:
        num = normalize_article_ref(r)
        if num in seen:
            continue
        seen.add(num)
        for a in corpus.find(document if document != "規約" else "規約", num) or corpus.find("規約", num):
            out.append({"source": "今の規約" if document == "規約" else document, "ref": a.label,
                        "caption": getattr(a, "caption", "") or "", "text": a.text()})
    return out[:8]


def _definitions(corpus, text: str) -> list[dict]:
    """今の規約で言葉を定義している条（「以下「対象物件」という。」など）のうち、text に出てくる言葉の条。

    直した文の確認で、AI が定義を推測で書いて人に確認を頼まないよう、今の規約の文を渡す（想定ユーザーでの確認で分かった）。
    """
    out, seen = [], set()
    for a in corpus.main.articles:
        body = a.text()
        terms = re.findall(r"以下[、]?「([^」]{1,20})」という", body)
        if any(t in text for t in terms) and a.label not in seen:
            seen.add(a.label)
            out.append({"source": "今の規約", "ref": a.label, "caption": getattr(a, "caption", "") or "",
                        "text": body + "\n（定義している言葉：" + "、".join(t for t in terms if t in text) + "）"})
    return out[:6]


def _review_edits(work_id: str, keys: list[str]) -> None:
    """直した条を1条ずつ AI に確かめてもらい、終わるたびに保存する。最後に資料の印を書き直す。"""
    from core.editcheck import cost_usd, review_edit

    for key in keys:
        work = store.load(work_id)
        e = (work.get("human_edits") or {}).get(key)
        if not e:
            continue
        text = e["text"]

        def begin(data: dict, key=key) -> None:  # 順番待ちから「確かめています」に（画面に経過時間を出すため）
            r = ((data.get("human_edits") or {}).get(key) or {}).get("review")
            if r:
                r.update(queued=False, started=__import__("datetime").datetime.now().isoformat(timespec="seconds"))
        store.mutate(work_id, begin)
        try:
            review, usage = review_edit(_review_material(work_id, work, key))
            usd = cost_usd(usage)
            result = {"status": "済み", "for_text": text, "at": _now(), "verdict": review.verdict, "summary": review.summary,
                      "concerns": [c.model_dump() for c in review.concerns], "cost_usd": usd}
            store.append_log(work_id, "edit", f"委員会で直した{key.split('|', 1)[1]}を AI が確かめました：{review.verdict}")
        except Exception as err:  # 1条確かめられなくても、残りの条は確かめる
            usd = 0.0
            result = {"status": "失敗", "for_text": text, "at": _now(), "error": f"{type(err).__name__}"}
            store.append_log(work_id, "error", f"委員会で直した{key.split('|', 1)[1]}を確かめられませんでした：{type(err).__name__}")

        def save(data: dict, key=key, result=result, usd=usd) -> None:
            e2 = (data.get("human_edits") or {}).get(key)
            if e2 is not None:
                e2["review"] = result
            if usd:
                data.setdefault("costs", []).append(_cost_entry(f"直した文の確認（{key.split('|', 1)[1]}）",
                                                                {"amount": max(1, round(usd * 100)), "currency": "USD"}))
        store.mutate(work_id, save)
    work = store.load(work_id)
    if _draft(work):
        _write_taisho(work_id, work, _draft(work), _corpus(work_id))


@app.get("/works/{work_id}/articles/review-status")
def review_status(work_id: str):
    """AI が直した文を確かめ終わったか（画面が3秒ごとに聞き、終わったときだけ画面を切り替える）。"""
    work = _unstick_reviews(work_id, store.load(work_id))
    reviewing = any((e.get("review") or {}).get("status") == "確認中" for e in (work.get("human_edits") or {}).values())
    return JSONResponse({"reviewing": reviewing})


@app.post("/works/{work_id}/articles/review")
async def review_articles(request: Request, work_id: str):
    """委員会で直した条を、AI に確かめてもらう（押したときだけ。1条あたり数セント）。key がなければ、確認前の条をまとめて。"""
    from core.editcheck import label

    form = await request.form()
    work = _unstick_reviews(work_id, store.load(work_id))
    edits = work.get("human_edits") or {}
    if any((e.get("review") or {}).get("status") == "確認中" for e in edits.values()):
        raise HTTPException(409, "AI が確かめている最中です。終わるまでお待ちください。")
    key = str(form.get("key", ""))
    keys = [key] if key in edits else [k for k, e in edits.items() if "確認前" in label(e)]
    if not keys:
        raise HTTPException(400, "確かめる条がありません。")

    started = __import__("datetime").datetime.now().isoformat(timespec="seconds")

    def mark(data: dict) -> None:  # 1条目は押した直後から「確かめています」、2条目からは順番待ち
        for i, k in enumerate(keys):
            data["human_edits"][k]["review"] = {"status": "確認中", "queued": i > 0, "queued_at": started,
                                                "started": "" if i else started,
                                                "for_text": data["human_edits"][k]["text"], "at": _now()}
    store.mutate(work_id, mark)
    threading.Thread(target=_review_edits, args=(work_id, keys), daemon=True).start()
    return RedirectResponse(f"/works/{work_id}/articles#row-top", status_code=303)



REVIEW_STUCK_SEC = 300  # 1条はふつう20〜60秒。これだけたっても進まなければ、処理が消えたとみなす（サーバーの再起動など）


def _unstick_reviews(work_id: str, work: dict) -> dict:
    """止まったまま残った「確認中」を「中断」にする。処理が消えても、画面からもう一度押せるように。"""
    from datetime import datetime

    def age(r: dict) -> float:
        t = r.get("started") or r.get("queued_at")
        try:
            return (datetime.now() - datetime.fromisoformat(t)).total_seconds() if t else REVIEW_STUCK_SEC + 1
        except ValueError:
            return REVIEW_STUCK_SEC + 1

    jobs = {k: e["review"] for k, e in (work.get("human_edits") or {}).items() if (e.get("review") or {}).get("status") == "確認中"}
    if not jobs:
        return work
    active = [r for r in jobs.values() if not r.get("queued")]
    # 確かめている条が長く進まない、または、確かめている条がないのに順番待ちだけが残っている
    stuck = (active and max(age(r) for r in active) > REVIEW_STUCK_SEC) or (not active and min(age(r) for r in jobs.values()) > 60)
    if not stuck:
        return work

    def stop(data: dict) -> None:
        for e in (data.get("human_edits") or {}).values():
            if (e.get("review") or {}).get("status") == "確認中":
                e["review"]["status"] = "中断"
    store.append_log(work_id, "error", "直した文の確認が途中で止まりました（サーバーの再起動など）")
    return store.mutate(work_id, stop)


def _review_progress(human: dict) -> dict | None:
    """AI が確かめている間の進み具合（何条のうち何条目か、今の条を確かめ始めてからの秒数）。"""
    from datetime import datetime

    jobs = [(k, e["review"]) for k, e in human.items() if (e.get("review") or {}).get("status") == "確認中"]
    if not jobs:
        return None
    active = next(((k, r) for k, r in jobs if not r.get("queued")), None)
    elapsed = 0
    if active and active[1].get("started"):
        try:
            elapsed = max(0, int((datetime.now() - datetime.fromisoformat(active[1]["started"])).total_seconds()))
        except ValueError:
            elapsed = 0
    return {"left": len(jobs), "active": active[0].split("|", 1)[1] if active else "", "elapsed": elapsed,
            "started": active[1].get("started", "") if active else ""}


# ---- ととのう規約に相談する（AI 相談）。画面は app/consult_app.py -------------------------
from app import consult_app  # noqa: E402

consult_app.register(app, templates, _corpus, latest_corpus, has_latest)
