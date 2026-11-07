"""②これからの見直し（計画E2a）のテスト。API は呼ばない。"""

from core.minaoshi import clean, rows, state, summary
from tests.test_partial import board_work  # noqa: F401  (pytest の fixture)

T = {"rows": [
    {"kind": "ほぼ同じ", "number": "1", "label": "第1条", "caption": "目的", "std_label": "第1条", "std_caption": "目的", "amount": "", "ratio": 1.0, "text": "a"},
    {"kind": "違う", "number": "37", "label": "第37条", "caption": "役員", "std_label": "第35条", "std_caption": "役員", "amount": "中", "ratio": 0.79, "text": "b"},
    {"kind": "今の規約だけ", "number": "31", "label": "第31条", "caption": "町内会費", "std_label": "", "std_caption": "", "amount": "", "ratio": 0.0, "text": "c"}],
    "missing": [{"number": "31の3", "label": "第31条の3", "caption": "国内管理人", "chapter": "", "text": "d"}]}


def test_rows_states_and_summary():
    rs = rows(T, touched={"37"})
    assert [r["id"] for r in rs] == ["c37", "c31", "s31の3"] and rs[0]["touched"]       # ほぼ同じは出さない
    assert rs[2]["std_text"] == "d"                                                      # 標準管理規約の文も持つ
    assert [r["id"] for r in rows(T, added={"31の3"})] == ["c37", "c31"]                # 今回の改正で足す条は判断の行に入れない
    dec = {"c37": {"d": "今のまま", "w": "", "m": ""}, "c31": {"d": "見直す", "w": "later", "m": "総会で"},
           "s31の3": {"d": "足す", "w": "", "m": ""}}
    assert [state(dec.get(r["id"])) for r in rs] == ["keep", "later", "later"]          # 見直す判断は宿題になる
    s = summary(rs, dec)
    assert s["counts"] == {"now": 0, "later": 2, "keep": 1, "undecided": 0}
    assert s["lists"]["later"][0]["name"] == "第31条" and s["lists"]["later"][0]["m"] == "総会で"
    assert s["lists"]["keep"][0]["name"] == "第37条"
    assert clean("違う", "なくす", "later") == ("", "")             # その行で選べない判断は捨てる
    assert clean("今の規約だけ", "残す", "later") == ("残す", "")    # 今のまま・残す・足さないは時期を持たない
    assert clean("標準にない", "足す", "now") == ("足す", "later")   # 今回入れるはまだ選べない（宿題になる）


def test_minaoshi_page_and_save(board_work):
    """②のページ：①との切り替え、判断の保存と集計、宿題の一覧の印刷。"""
    M, store, c, wid, _, _ = board_work
    page = c.get(f"/works/{wid}/minaoshi").text
    assert "これからの見直し" in page and f'href="/works/{wid}"' in page and 'aria-current="page"' in page
    assert "今回の改定案に入れる" not in page and "標準管理規約の文を見る" in page        # まだ働かない選択肢は出さない
    from core.minaoshi import rows as mrows
    rs = mrows(M._taiou(wid), M._touched(store.load(wid)), M._added(store.load(wid)))
    miss = next(r for r in rs if r["type"] == "標準にない")
    r = c.post(f"/works/{wid}/minaoshi", data={"id": miss["id"], "d": "足す", "m": "次の総会で"},
               headers={"accept": "application/json"})
    assert r.status_code == 200 and r.json()["counts"]["later"] == 1
    assert store.load(wid)["minaoshi"][miss["id"]]["d"] == "足す"
    assert "次の総会で" in c.get(f"/works/{wid}/minaoshi/shukudai").text
    c.post(f"/works/{wid}/minaoshi", data={"id": miss["id"], "d": "", "m": "残ったメモ"}, headers={"accept": "application/json"})
    assert miss["id"] not in store.load(wid)["minaoshi"]                               # 未判断に戻すとメモも含めて消す
    assert c.post(f"/works/{wid}/minaoshi", data={"id": "nope", "d": "足す"}).status_code == 400
