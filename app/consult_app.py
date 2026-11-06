"""画面：ととのう規約に相談する（AI 相談）。core/consult.py を使う。

- 質問する／文章を確かめる（ニュース原稿・議事録・説明文などを貼る）
- マンションの基本情報（住戸の数・組合員の数・議決権の総数）を入れておく場所。数の計算に使う。
  足りないまま数を聞かれたら、答えの画面で記入を促し、入れたらもう一度答えてもらえる
- 相談は1件ずつ記録し（private/consult/）、続けて質問できる。貼った文は人名を伏せて送れる
"""

from __future__ import annotations

import re
import threading
import traceback
from datetime import datetime

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app import store
from core import consult as C
from core.config import MissingApiKey
from core.review import JST

RUNNING: set[str] = set()   # このサーバーで考え中の相談（再起動で消えた処理を見分ける）
STEP_WORDS = {"list_topics": "改正の論点を確かめています", "get_law_articles": "区分所有法の条文を読んでいます",
              "get_standard_articles": "標準管理規約を読んでいます", "get_building_info": "マンションの基本情報を見ています",
              "calc_votes": "定足数と賛成の数を計算しています", "list_articles": "お使いの規約を見ています",
              "get_articles": "お使いの規約の条を読んでいます", "record_answer": "答えをまとめています"}
MODES = {"ask": "質問する", "check": "文章を確かめる"}
AI_NOTE = ("ととのう規約の資料（区分所有法・標準管理規約・改正の論点・お使いの規約）を AI が読んで答えます。\n"
           "1〜3分ほど・1回 約$0.1〜0.5（十数円〜80円ほど）。\n"
           "費用は、このツールに登録した AI の利用料（APIキー）として請求されます（$1 は約150円）。よろしいですか？")


def _now() -> str:
    return datetime.now(JST).strftime("%m月%d日 %H:%M")


def _new_id() -> str:
    return store.new_id()


def profile_line(p: dict) -> str:
    if not p or C.missing(p):
        return ""
    s = f"{p['units']}戸・組合員 {p['owners']}・議決権 {p['votes_total']}（{p.get('vote_rule', '分からない')}）"
    return s


def register(app, templates, corpus_for) -> None:
    """ルートを登録する。corpus_for(work_id) は照らす規約（core.corpus.Corpus）を返す関数。"""
    templates.env.globals["profile_line"] = profile_line
    templates.env.globals["consult_counts"] = C.counts

    def _stopped(data: dict) -> bool:
        return any(t.get("status") == "考え中" for t in data.get("turns", [])) and data["id"] not in RUNNING

    def _mark_stopped(data: dict) -> dict:
        if not _stopped(data):
            return data

        def fn(d):
            for t in d.get("turns", []):
                if t.get("status") == "考え中":
                    t["status"], t["error"] = "エラー", "途中で止まりました（サーバーの再起動など）。下の「もう一度答えてもらう」を押してください。"
        return store.update_consult(data["id"], fn)

    def _run(cid: str, n: int) -> None:
        RUNNING.add(cid)
        try:
            data = store.load_consult(cid)
            turn = data["turns"][n]
            profile = store.load_profile()
            corpus = None
            if data.get("work_id"):
                try:
                    corpus = corpus_for(data["work_id"])
                except Exception:  # 作業が消えていても、規約なしで答える
                    corpus = None
            history = [{"question": t.get("question", ""), "summary": (t.get("answer_masked") or {}).get("summary", "")}
                       for t in data["turns"][:n] if t.get("status") == "済み"]

            def step(name):
                store.update_consult(cid, lambda d: d["turns"][n].__setitem__("step", STEP_WORDS.get(name, "考えています")))

            text = data.get("sent_text", "")
            answer, cost, calls = C.consult(turn["mode"], text, turn.get("sent_question", turn.get("question", "")),
                                            profile=profile, corpus=corpus, history=history, on_step=step)
            shown = C.unmask(answer, data.get("mapping") or {})

            def done(d):
                t = d["turns"][n]
                t.update(status="済み", answer=shown, answer_masked=answer, cost=cost, tools=calls, done_at=_now(), step="",
                         profile_used=profile_line(profile) if "calc_votes" in calls or "get_building_info" in calls else "")
                d["cost_total"] = round(sum(x.get("cost") or 0 for x in d["turns"]), 4)
            store.update_consult(cid, done)
        except Exception as e:  # 画面に出す（APIキーの値などは出さない）
            traceback.print_exc()
            msg = "APIキーが設定されていません。" if isinstance(e, MissingApiKey) else f"AI の呼び出しでエラーになりました（{type(e).__name__}）。"
            store.update_consult(cid, lambda d: d["turns"][n].update(status="エラー", error=msg + "少し待ってから「もう一度答えてもらう」を押してください。", step=""))
        finally:
            RUNNING.discard(cid)

    def _start(cid: str, n: int) -> None:
        RUNNING.add(cid)
        threading.Thread(target=_run, args=(cid, n), daemon=True).start()

    def _mask(text: str, question: str, masked: bool, profile: dict, more: str = "") -> tuple[str, str, dict]:
        if not masked:
            return text, question, {}
        extra = [profile.get("name", "")] if profile.get("name") else []
        extra += [w.strip() for w in re.split(r"[、,，\s]+", more or "") if len(w.strip()) >= 2]
        joined, mapping = C.mask_names(text + "\n␞\n" + question, extra)
        t, _, q = joined.partition("\n␞\n")
        return t, q, mapping

    @app.get("/consult", response_class=HTMLResponse)
    def consult_home(request: Request, work: str = "", saved: str = ""):
        profile = store.load_profile()
        works = [w for w in store.list_works() if w.get("findings")]
        return templates.TemplateResponse(request, "consult.html", {
            "profile": profile, "missing": C.missing(profile), "works": works, "consults": store.list_consults(),
            "work_id": work or profile.get("work_id", ""), "saved": saved, "vote_rules": C.VOTE_RULES, "ai_note": AI_NOTE,
            "modes": MODES})

    @app.post("/consult/profile")
    async def save_profile(request: Request):
        form = await request.form()
        profile = C.clean_profile(dict(form))
        store.save_profile(profile)
        nxt = str(form.get("next") or "")
        if nxt.startswith("/consult/") and nxt[9:].replace("-", "").isalnum():
            if form.get("rerun"):
                return RedirectResponse(f"{nxt}/rerun", status_code=307)
            return RedirectResponse(f"{nxt}?saved=profile", status_code=303)
        return RedirectResponse("/consult?saved=profile#profile", status_code=303)

    @app.post("/consult")
    async def new_consult(request: Request):
        form = await request.form()
        mode = form.get("mode") if form.get("mode") in MODES else "ask"
        text = str(form.get("text") or "").replace("\r\n", "\n").strip()
        question = str(form.get("question") or "").replace("\r\n", "\n").strip()
        if mode == "check" and not text:
            return RedirectResponse("/consult?saved=empty_text", status_code=303)
        if mode == "ask" and not question:
            return RedirectResponse("/consult?saved=empty_question", status_code=303)
        work_id = str(form.get("work_id") or "")
        if work_id:
            try:
                store.load(work_id)
            except store.WorkNotFound:
                work_id = ""
        profile = store.load_profile()
        masked = bool(form.get("mask"))
        sent_text, sent_q, mapping = _mask(text[:20000], question[:2000], masked, profile, str(form.get("mask_more") or ""))
        first = next((ln.strip(" ◆■●・　") for ln in (text if mode == "check" else question).split("\n") if ln.strip(" ◆■●・　")), "")
        title = (first[:40] + ("…" if len(first) > 40 else "")) or "相談"
        cid = _new_id()
        work_name = ""
        if work_id:
            work_name = store.load(work_id).get("name", "")
        store.save_consult({"id": cid, "created": _now(), "mode": mode, "title": title, "text": text, "question": question,
                            "sent_text": sent_text, "mapping": mapping, "masked": masked, "work_id": work_id, "work_name": work_name,
                            "turns": [{"mode": mode, "question": question, "sent_question": sent_q, "status": "考え中",
                                       "at": _now(), "step": "準備をしています"}], "cost_total": 0})
        _start(cid, 0)
        return RedirectResponse(f"/consult/{cid}", status_code=303)

    @app.get("/consult/{cid}", response_class=HTMLResponse)
    def show_consult(request: Request, cid: str, saved: str = ""):
        data = _mark_stopped(store.load_consult(cid))
        profile = store.load_profile()
        return templates.TemplateResponse(request, "consult_view.html", {
            "c": data, "profile": profile, "works": [w for w in store.list_works() if w.get("findings")], "missing": C.missing(profile), "vote_rules": C.VOTE_RULES, "ai_note": AI_NOTE,
            "saved": saved, "modes": MODES, "busy": any(t.get("status") == "考え中" for t in data["turns"])})

    @app.get("/consult/{cid}/status")
    def consult_status(cid: str):
        data = _mark_stopped(store.load_consult(cid))
        last = data["turns"][-1]
        return JSONResponse({"status": last.get("status"), "step": last.get("step", ""), "turns": len(data["turns"])})

    @app.post("/consult/{cid}/ask")
    async def follow_up(request: Request, cid: str):
        form = await request.form()
        question = str(form.get("question") or "").replace("\r\n", "\n").strip()
        data = store.load_consult(cid)
        if not question or any(t.get("status") == "考え中" for t in data["turns"]):
            return RedirectResponse(f"/consult/{cid}", status_code=303)
        _, sent_q, mapping = _mask("", question[:2000], data.get("masked"), store.load_profile())
        merged = {**(data.get("mapping") or {})}
        # 続けての質問で新しく伏せた名前は、前の記号と重ならないように付け直す
        for tok, word in mapping.items():
            existing = next((k for k, v in merged.items() if v == word), None)
            if existing:
                sent_q = sent_q.replace(tok, existing)
            elif tok in merged:
                new = f"{tok}{len(merged) + 1}"
                sent_q, merged[new] = sent_q.replace(tok, new), word
            else:
                merged[tok] = word

        def fn(d):
            d["mapping"] = merged
            d["turns"].append({"mode": "ask", "question": question, "sent_question": sent_q, "status": "考え中", "at": _now(),
                               "step": "準備をしています"})
        data = store.update_consult(cid, fn)
        _start(cid, len(data["turns"]) - 1)
        return RedirectResponse(f"/consult/{cid}#turn-{len(data['turns'])}", status_code=303)

    @app.post("/consult/{cid}/rerun")
    def rerun(cid: str):
        """最後の質問に、もう一度答えてもらう（基本情報を入れたあと・エラーのあと）。"""
        data = store.load_consult(cid)
        if any(t.get("status") == "考え中" for t in data["turns"]):
            return RedirectResponse(f"/consult/{cid}", status_code=303)
        last = data["turns"][-1]

        def fn(d):
            if last.get("status") == "エラー":
                d["turns"][-1].update(status="考え中", error="", step="準備をしています", at=_now())
            else:
                d["turns"].append({"mode": last["mode"], "question": last.get("question", ""), "sent_question": last.get("sent_question", ""),
                                   "status": "考え中", "at": _now(), "step": "準備をしています", "rerun": True})
        data = store.update_consult(cid, fn)
        _start(cid, len(data["turns"]) - 1)
        return RedirectResponse(f"/consult/{cid}#turn-{len(data['turns'])}", status_code=303)

    @app.post("/consult/{cid}/delete")
    def delete(cid: str):
        store.delete_consult(cid)
        return RedirectResponse("/consult?saved=deleted#history", status_code=303)

