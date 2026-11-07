"""ととのう規約に相談する（AI 相談）。API は呼ばない（偽の AI で道具の流れと画面を確かめる）。"""

import json
import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from core import consult as C
from tests.test_partial import board_work  # noqa: F401  (pytest の fixture)


def test_votes_for_65_units():
    p = C.clean_profile({"units": "６５", "vote_rule": "1戸1議決権"})
    assert (p["owners"], p["votes_total"]) == (65, 65)
    sp = C.votes(p, "特別決議")
    assert sp["定足数"]["組合員"] == 33 and sp["定足数"]["議決権"] == 33
    assert sp["計算"][0]["必要な賛成"] == {"組合員": 25, "議決権": 25}      # 33人出席 → 25人の賛成
    assert sp["計算"][1]["必要な賛成"] == {"組合員": 49, "議決権": 49}      # 全員出席
    assert "49" in sp["改正前との比べ"]["改正前（2026年3月までに招集した総会）"]
    assert C.votes(p, "普通決議", 40, 40)["計算"][0]["必要な賛成"] == {"議決権": 21}
    assert C.votes(p, "3分の2の決議")["計算"][0]["必要な賛成"]["組合員"] == 22
    assert C.votes(p, "建替え決議")["必要な賛成"]["原則（各5分の4以上）"]["組合員"] == 52
    assert C.votes(p, "特別決議", 30, 30)["計算"][0]["総会が成立するか"] == "定足数に足りない"


def test_votes_need_profile_and_area_based_votes():
    assert C.votes({}, "特別決議")["need"] == ["住戸の数", "組合員（区分所有者）の数", "議決権の総数"]
    p = C.clean_profile({"units": "40", "owners": "38", "vote_rule": "専有面積の割合など"})
    assert C.missing(p) == ["議決権の総数"]                     # 面積割合なら総数は推測しない
    p = C.clean_profile({"units": "40", "owners": "38", "votes_total": "10000", "vote_rule": "専有面積の割合など"})
    assert C.votes(p, "特別決議")["定足数"] == {"組合員": 20, "議決権": 5001, "説明": "組合員の過半数、かつ議決権の過半数が出席"}


def test_mask_names_and_unmask():
    text = "木下氏も評価。山田さんと鈴木理事長、木村先生、管理員さんにも。サンプル台マンションの規約。"
    masked, mapping = C.mask_names(text, ["サンプル台マンション"])
    assert not any(n in masked for n in ("木下", "山田", "鈴木", "木村", "サンプル台"))
    assert "管理員さん" in masked
    assert C.unmask(masked, mapping) == text
    assert C.unmask({"a": [masked]}, mapping) == {"a": [text]}


def _handler():
    return C.Handler(profile=C.clean_profile({"units": "65", "vote_rule": "1戸1議決権"}), pasted="新：総会出席者の4分の3以上の賛成が必要")


def test_record_answer_requires_reading_the_cited_article():
    """読んでいない条を根拠にした答えは受け付けない。読めば受け付ける。根拠のない断定は「資料の外」に下げる。"""
    h = _handler()
    item = {"quote": "総会出席者の4分の3以上", "verdict": "正しい", "comment": "c", "basis": [{"source": "区分所有法", "ref": "第31条第1項"}]}
    r = json.loads(h.run("record_answer", {"summary": "s", "items": [item]}))
    assert "受け付けませんでした" in r and h.answer is None
    h.run("get_law_articles", {"articles": ["第31条"]})
    r = json.loads(h.run("record_answer", {"summary": "s", "items": [item, {"verdict": "誤り", "comment": "根拠なし", "basis": []}]}))
    assert "受け付けませんでした" in r                          # 根拠のない「誤り」
    r = json.loads(h.run("record_answer", {"summary": "s", "items": [item, {"verdict": "誤り", "comment": "根拠なし", "basis": []}]}))
    assert r == {"受け付けました": 2}                            # 3回目は受け付け、根拠のない項目は下げる
    assert [i["verdict"] for i in h.answer["items"]] == ["資料の外", "正しい"] and h.answer["items"][1]["quote_found"]


def test_calc_basis_needs_calc_tool():
    h = _handler()
    assert h.check_basis({"source": "計算", "ref": "特別決議"})
    h.run("calc_votes", {"kind": "特別決議"})
    assert not h.check_basis({"source": "計算", "ref": "特別決議"})
    assert h.check_basis({"source": "区分所有法", "ref": "第999条"}) == "区分所有法にこの条はありません"


class _Block(SimpleNamespace):
    def model_dump(self, exclude_none=False):
        return {k: v for k, v in vars(self).items()}


class _FakeClient:
    """道具を順に呼んでから答えを記録する、偽の AI。"""

    def __init__(self, script):
        self.script = list(script)
        self.sent = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **kw):
        self.sent.append(kw)
        uses = self.script.pop(0)
        content = [_Block(type="tool_use", id=f"t{i}", name=n, input=a) for i, (n, a) in enumerate(uses)]
        msg = SimpleNamespace(content=content, stop_reason="tool_use",
                              usage=SimpleNamespace(model_dump=lambda: {"input_tokens": 1000, "output_tokens": 200}))

        class S:
            def __enter__(s):
                return SimpleNamespace(get_final_message=lambda: msg)

            def __exit__(s, *a):
                return False
        return S()


ANSWER = {"summary": "おおむね正しいです。", "items": [
    {"quote": "総会出席者の4分の3以上", "verdict": "言い方に注意", "comment": "定足数（33戸）も要ります。最少25戸の賛成です。",
     "basis": [{"source": "区分所有法", "ref": "第31条第1項"}, {"source": "計算", "ref": "特別決議"}],
     "suggestion": "33戸以上が出席（書面・委任状を含む）し、その4分の3以上の賛成"}],
    "need_info": [], "followups": ["総会の案内にどう書けばよいですか？"]}


def test_consult_loop_with_fake_ai(monkeypatch):
    fake = _FakeClient([[("list_topics", {}), ("get_law_articles", {"articles": ["31"]})],
                        [("calc_votes", {"kind": "特別決議"})],
                        [("record_answer", ANSWER)]])
    monkeypatch.setattr(C, "client", lambda: fake)
    steps = []
    ans, cost, calls = C.consult("check", "新：総会出席者の4分の3以上の賛成が必要", "", profile=C.clean_profile({"units": "65", "vote_rule": "1戸1議決権"}),
                                 on_step=steps.append)
    assert calls == ["list_topics", "get_law_articles", "calc_votes", "record_answer"] and steps == calls
    assert ans["items"][0]["verdict"] == "言い方に注意" and cost > 0
    # 道具の結果を AI に返している（計算はアプリが出す）
    results = [r for m in fake.sent[-1]["messages"] if m["role"] == "user" and isinstance(m["content"], list) for r in m["content"]]
    assert any('"組合員": 25' in r["content"] for r in results)


@pytest.fixture
def app_client(monkeypatch):
    import app.main as M
    from app import consult_app

    def fake_consult(mode, text, question, *, profile, corpus=None, history=None, effort="medium", on_step=None, rules="原本"):
        if on_step:
            on_step("get_law_articles")
        need = C.missing(profile)
        ans = C.finalize({**ANSWER, "summary": f"人物Aさんの原稿について。{len(history or [])}", "need_info": need}, None, text)
        return ans, 0.12, ["record_answer"]

    monkeypatch.setattr(C, "consult", fake_consult)
    consult_app.RUNNING.clear()
    return TestClient(M.app)


def _wait(c, cid):
    for _ in range(50):
        if c.get(f"/consult/{cid}/status").json()["status"] != "考え中":
            return
        time.sleep(0.05)


def test_consult_pages_flow(app_client):
    from app import store

    c = app_client
    page = c.get("/consult").text
    assert "ととのう規約に相談する" in page and "マンションの基本情報" in page and 'name="units"' in page
    assert 'href="/consult"' in c.get("/").text                       # ヘッダーから開ける
    # 文章を確かめる（人名を伏せて送る）
    r = c.post("/consult", data={"mode": "check", "text": "山田さんの原稿。総会出席者の4分の3以上", "question": "", "mask": "1"},
               follow_redirects=False)
    cid = r.headers["location"].rsplit("/", 1)[1]
    _wait(c, cid)
    d = store.load_consult(cid)
    assert "山田" not in d["sent_text"] and d["mapping"]["人物A"] == "山田"
    assert d["turns"][0]["answer"]["summary"].startswith("山田さんの原稿")     # 答えでは名前を戻す
    view = c.get(f"/consult/{cid}").text
    assert "言い方に注意" in view and "直し案" in view and "返信用にコピー" in view
    # 基本情報が足りない → 記入を促し、入れるともう一度答える
    assert "マンションの基本情報が足りない" in view and 'name="rerun"' in view
    r = c.post("/consult/profile", data={"units": "65", "vote_rule": "1戸1議決権", "next": f"/consult/{cid}", "rerun": "1"},
               follow_redirects=True)
    _wait(c, cid)
    d = store.load_consult(cid)
    assert len(d["turns"]) == 2 and d["turns"][1]["rerun"] and d["turns"][1]["answer"]["need_info"] == []
    assert store.load_profile()["votes_total"] == 65
    # 続けて質問する（前のやり取りを渡す）
    c.post(f"/consult/{cid}/ask", data={"question": "案内にはどう書く？"})
    _wait(c, cid)
    d = store.load_consult(cid)
    assert d["turns"][2]["answer"]["summary"].endswith("2") and d["cost_total"] == pytest.approx(0.36)
    assert "やり取り 3回" in c.get("/consult").text
    c.post(f"/consult/{cid}/delete")
    assert store.list_consults() == []


def test_empty_inputs_and_stopped_turns(app_client):
    from app import consult_app, store

    c = app_client
    assert "確かめる文章を貼ってください" in c.get(c.post("/consult", data={"mode": "check", "text": ""}, follow_redirects=False)
                                                .headers["location"]).text
    store.save_consult({"id": "20261106-000000-aaaaaa", "created": "x", "mode": "ask", "title": "t", "text": "", "question": "q",
                        "sent_text": "", "mapping": {}, "masked": False, "work_id": "", "turns": [{"mode": "ask", "question": "q", "status": "考え中"}]})
    consult_app.RUNNING.discard("20261106-000000-aaaaaa")
    view = c.get("/consult/20261106-000000-aaaaaa").text
    assert "途中で止まりました" in view and "もう一度答えてもらう" in view



def test_work_page_links_to_consult_with_its_rules(board_work):
    """作業の画面から「この規約について相談する」で、その規約を選んだ状態の相談の画面を開ける。"""
    M, store, c, wid, _, _ = board_work
    assert f'href="/consult?work={wid}"' in c.get(f"/works/{wid}").text
    assert f'<option value="{wid}" selected' in c.get(f"/consult?work={wid}").text


def test_mask_names_after_roles_without_honorifics():
    """「記録：中川」「出席：田中、鈴木」のように敬称のない名前も伏せ、同じ名前は文中のどこでも伏せる（想定ユーザーでの確認で分かった）。"""
    masked, mapping = C.mask_names("講師：森田一郎氏（管理士）、記録：中川。中川から説明。出席：田中、鈴木（監事）。記録：理事会")
    assert not any(n in masked for n in ("森田", "中川", "田中", "鈴木")) and "記録：理事会" in masked
    assert set(mapping.values()) == {"森田一郎", "中川", "田中", "鈴木"}


def test_reply_copy_and_profile_used(app_client):
    from app import store

    c = app_client
    store.save_profile(C.clean_profile({"units": "48", "vote_rule": "1戸1議決権"}))
    r = c.post("/consult", data={"mode": "check", "text": "記録：中川。総会出席者の4分の3以上", "mask": "1", "mask_more": "305号室"},
               follow_redirects=False)
    cid = r.headers["location"].rsplit("/", 1)[1]
    _wait(c, cid)
    view = c.get(f"/consult/{cid}").text
    assert "人名を伏せて送りました（" in view and "中川 → 人物A" in view
    assert 'lines.push("   （根拠：" + bs.join("、")' in view          # 返信用の文で根拠を区切る
    page = c.get("/consult").text
    assert 'class="bar"' not in page and "ほかに伏せる語" in page   # 帯が基本情報の保存ボタンを隠さない


def test_today_is_given_and_results_sorted_by_importance():
    """AI に今日の日付を渡す（「来年4月から」を今日基準で読む）。結果は誤りを先に（想定ユーザーでの確認で分かった）。"""
    from datetime import date

    assert "2026年11月6日（金）" in C.today_line(date(2026, 11, 6)) and "すでに施行" in C.today_line(date(2026, 11, 6))
    assert "施行（2026年4月1日）より前" in C.today_line(date(2026, 2, 1))
    assert C.user_message("check", "t", "", [], False, today=date(2026, 11, 6)).startswith("# 今日")
    ans = C.finalize({"summary": "s", "items": [
        {"quote": "a", "verdict": "資料の外", "comment": "", "basis": []},
        {"quote": "b", "verdict": "誤り", "comment": "", "basis": [{"source": "貼った文", "ref": "x"}]},
        {"quote": "c", "verdict": "言い方に注意", "comment": "", "basis": [{"source": "貼った文", "ref": "x"}]}]}, None, "a b c")
    assert [i["verdict"] for i in ans["items"]] == ["誤り", "言い方に注意", "資料の外"]
    p = C.clean_profile({"units": "48", "owners": "116", "votes_total": "10000", "vote_rule": "1戸1議決権"})
    assert (p["owners"], p["votes_total"]) == (48, 48)        # 1戸1議決権に戻したら、前の数を残さない


def test_more_words_and_work_labels():
    """ほかに伏せる語は「伏せた語A」に（マンション名とは別の記号）。同じ名前の作業を作成日時と ID の末尾で見分ける（2回目の確認で分かった）。"""
    from app.consult_app import work_label

    masked, mapping = C.mask_names("講師：木村先生（架空）。305号室の方。木村先生が説明。", ["サンプル台"], ["305号室"])
    assert mapping == {"伏せた語A": "305号室", "人物A": "木村"} and "人物A先生が説明" in masked
    assert work_label("20261103-200000-dm0001") == "11/3 20:00 作成・0001"
    assert work_label("20261103-990000-fed2b7") == "11/3 作成・d2b7"      # ありえない時刻は出さない


def test_follow_up_masks_names_known_from_the_first_text(app_client):
    """続けての質問で、最初の文で伏せた名前を敬称なしで書いても、AI には記号で送る。"""
    from app import store

    c = app_client
    r = c.post("/consult", data={"mode": "check", "text": "記録：中川。講師は山田氏。", "mask": "1", "mask_more": "305号室"},
               follow_redirects=False)
    cid = r.headers["location"].rsplit("/", 1)[1]
    _wait(c, cid)
    c.post(f"/consult/{cid}/ask", data={"question": "中川の件と、305号室の件、それから新しく田中さんの件"})
    _wait(c, cid)
    d = store.load_consult(cid)
    q = d["turns"][1]["sent_question"]
    assert not any(w in q for w in ("中川", "305号室", "田中")), q
    assert d["mapping"][q.split("の件")[0]] == "中川"


def test_auto_pull_waits_while_consulting():
    from pathlib import Path

    s = (Path(__file__).parents[1] / "scripts/codespace_serve.sh").read_text(encoding="utf-8")
    assert "private/consult" in s and '"status": "考え中"' in s


def test_consult_with_latest_rules(monkeypatch):
    """総会の結果を記録した作業は「最新の規約」（総会で可決した改定を反映）で照らせる（作者の依頼）。"""
    import shutil
    from pathlib import Path

    import app.main as M
    from app import consult_app, store

    src = Path(__file__).resolve().parent.parent / "data" / "public" / "persona_works" / "20261106-220948-f85ddb"
    wid = store.new_id()
    shutil.copytree(src, store.path(wid))
    got = {}

    def fake_consult(mode, text, question, *, profile, corpus=None, history=None, effort="medium", on_step=None, rules="原本"):
        got["rules"], got["corpus"] = rules, corpus
        return C.finalize({**ANSWER, "need_info": []}, None, text), 0.1, ["record_answer"]

    monkeypatch.setattr(C, "consult", fake_consult)
    consult_app.RUNNING.clear()
    c = TestClient(M.app)
    try:
        assert M.has_latest(wid)
        latest, orig = M.latest_corpus(wid), M._corpus(wid)
        assert len(latest.main.articles) > len(orig.main.articles)          # 総会で新設した条が入る
        assert [a for a in latest.main.articles if a.number == "49"][0].text() != [a for a in orig.main.articles if a.number == "49"][0].text()
        page = c.get("/consult").text
        assert f'value="{wid}|最新"' in page and "最新の規約（総会で可決した改定を含む）" in page
        r = c.post("/consult", data={"mode": "ask", "question": "定足数は？", "work_id": f"{wid}|最新"}, follow_redirects=False)
        cid = r.headers["location"].rsplit("/", 1)[1]
        _wait(c, cid)
        assert store.load_consult(cid)["rules"] == "最新" and got["rules"] == "最新"
        assert len(got["corpus"].main.articles) == len(latest.main.articles)
        assert "最新の規約</b>（総会で可決した改定を含む）" in c.get(f"/consult/{cid}").text
        # 原本を選んだときは、これまでどおり読み込んだ規約
        r = c.post("/consult", data={"mode": "ask", "question": "定足数は？", "work_id": wid}, follow_redirects=False)
        cid = r.headers["location"].rsplit("/", 1)[1]
        _wait(c, cid)
        assert got["rules"] == "原本" and len(got["corpus"].main.articles) == len(orig.main.articles)
    finally:
        shutil.rmtree(store.path(wid))


def test_latest_note_reaches_ai():
    m = C.user_message("ask", "", "q", [], True, rules="最新")
    assert "総会で可決した改定を反映した最新の規約" in m
    assert "読み込んだときの規約" in C.user_message("ask", "", "q", [], True)
