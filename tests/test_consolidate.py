"""最新の規約の組み立てと、総会の結果の記録のテスト。API は呼ばない。"""

import shutil
from datetime import date

from core.config import ROOT
from core.consolidate import consolidate, to_docx, to_text, wareki
from core.corpus import Corpus
from core.draft import Amendment
from core.ingest import load_collection

CORPUS = Corpus.from_collection(load_collection(ROOT / "evals/data/old_collection.txt"))


def amend(kind, article, caption, text, document="規約"):
    return Amendment(kind, article, None if kind == "新設" else article, caption, text, "", [], [], ["第1条"], document=document)


def test_consolidate_main():
    ams = [amend("改正", "第45条", "招集手続", "第45条　新しい招集手続。\n2　第2項。"),
           amend("新設", "第25条の2", "保険金等の請求及び受領等", "第25条の2　理事長は、保険金等を請求する。"),
           amend("削除", "第20条", "", "")]
    blocks = consolidate(CORPUS.main, ams, "○○マンション管理規約", date(2026, 5, 24), "第25期定期総会")
    text = to_text(blocks)
    assert text.startswith("○○マンション管理規約")
    assert "第45条　新しい招集手続。\n2　第2項。" in text and "前条第1項" in text  # 改正は差し替え、ほかの条は元のまま
    assert text.index("第25条　") < text.index("第25条の2　") < text.index("第26条　")  # 新設は番号の位置
    assert "第20条　削除" in text
    assert text.count("（招集手続）") == 1
    assert text.rstrip().endswith("この規約の改正は、令和8年5月24日から施行する。")
    assert "附　則（令和8年5月24日　第25期定期総会改正）" in text and "平成12年4月1日" in text  # 元の附則も残す
    assert sum(1 for b in blocks if b.kind == "chapter") == len({a.chapter for a in CORPUS.main.articles})
    assert to_docx(blocks)[:2] == b"PK"
    assert wareki(date(2026, 4, 1)) == "令和8年4月1日" and wareki(date(2019, 5, 1)) == "令和元年5月1日"


def test_consolidate_item_style_rules():
    rule = CORPUS.get("○○マンションペット飼育細則")
    blocks = consolidate(rule, [amend("改正", "2.", "飼育者の遵守事項", "2.　\n(1)　迷惑をかけないこと。")],
                         "○○マンションペット飼育細則", date(2026, 5, 24))
    text = to_text(blocks)
    assert "2. 飼育者の遵守事項\n(1)　迷惑をかけないこと。" in text and "1. 飼育できる動物" in text
    assert "この細則の改正は" in text


def test_meeting_flow(monkeypatch):
    from fastapi.testclient import TestClient

    import app.main as M
    from app import store

    draft = {"amendments": [amend("改正", "第45条", "招集手続", "第45条　新しい招集手続。").to_dict(),
                            amend("削除", "第3条", "", "", document="○○マンション総会運営細則").to_dict(),
                            amend("改正", "第3条", "使用料", "第3条　使用料は月額9,000円。〔選択〕",
                                  document="○○マンション駐車場使用細則").to_dict()], "notes": ""}
    wid = store.new_id()
    d = store.path(wid)
    d.mkdir(parents=True)
    shutil.copy(ROOT / "evals/data/old_collection.txt", d / "source.txt")
    store.save(wid, {"name": "t", "info": {"型": "単棟型"}, "status": "説明文あり", "articles": 74, "log": [],
                     "documents": [{"kind": "規約", "title": "○○マンション管理規約", "articles": 74, "style": "条", "annotations": 0}],
                     "findings": [{"article": "第45条", "topic_id": "2-1", "category": "必須", "issue": "i", "current_excerpt": "",
                                   "law_basis": ["第35条"], "standard_basis": ["第43条"], "where": "規約", "proposal": "p"}],
                     "decisions": {"0": {"decision": "採用", "reason": ""}}, "draft": draft})
    try:
        c = TestClient(M.app)
        page = c.get(f"/works/{wid}").text
        assert "総会の結果と、最新の規約" in page and "管理規約の改定（" in page
        form = {"m_name": "第25期定期総会", "m_date": "2026-05-24", "m_effective": "",
                "m_result_0": "修正して可決", "m_edit_0_0": "第45条　総会で修正した招集手続。",
                "m_result_1": "否決", "m_result_2": "可決"}
        r = c.post(f"/works/{wid}/meeting", data=form, follow_redirects=False)
        assert r.status_code == 303 and r.headers["location"].endswith("#meeting")
        w = store.load(wid)
        assert w["meeting"]["results"]["規約"] == "修正して可決" and list(w["meeting"]["edits"]) == ["規約|第45条"]
        docs = M.final_documents(wid, w)
        assert [x["doc"] for x in docs] == ["規約", "○○マンション駐車場使用細則"]  # 否決した総会運営細則は作らない
        assert "総会で修正した招集手続" in to_text(docs[0]["blocks"])
        assert "特別決議により改正（第45条）" in docs[0]["history"] and "令和8年5月24日" in docs[0]["history"]
        assert docs[1]["left"] == ["駐車場使用細則 第3条"] and not docs[1]["blocks"]  # 〔選択〕が残れば作らない
        r = c.get(f"/works/{wid}/final/0.docx")
        assert r.status_code == 200 and r.content[:2] == b"PK" and "attachment" in r.headers["content-disposition"]
        assert "総会で修正した招集手続" in c.get(f"/works/{wid}/final/0/view").text
        assert c.get(f"/works/{wid}/final/1.docx").status_code == 404
        assert "最新の規約・細則" in c.get(f"/works/{wid}").text
    finally:
        shutil.rmtree(d)
