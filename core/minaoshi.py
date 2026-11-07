"""②これからの見直し：条の対応表の行ごとに、理事会の判断を記録する（計画E2a。AI は使わない）。

今回の改正（①。法改正に合わせる一部改正）とは別の場所。今の規約と標準管理規約の違いを見て、行ごとに
「今のまま・標準に合わせる」「残す・見直す・なくす」「足さない・足す」と、いつ扱うか（今回の改定案に入れる／次回以降の宿題）を決める。
今回の改定案に入れるにした行を ① に渡すのは計画E2b（まだ作らない）。宿題は印刷して、次の理事会・総会や全部改正の準備に使う。
"""

from __future__ import annotations

ACTIONS = {
    "違う": ["今のまま", "標準に合わせる"],
    "今の規約だけ": ["残す", "見直す", "なくす"],
    "標準にない": ["足さない", "足す"],
}
KEEP = {"今のまま", "残す", "足さない"}       # 見直さない判断
# いつ扱うか。今は宿題（次回以降）だけ。「今回の改定案に入れる」は、改定案に渡す仕組み（計画E2b）ができてから出す
# （選べるのに働かないと、改定案に入ったと思い込む。想定ユーザーでの確認から）
WHEN = {"later": "次回以降（宿題）"}


def rows(t: dict, touched: set | None = None, added: set | None = None) -> list[dict]:
    """判断が要る行（「ほぼ同じ」は除く）。id は今の規約の条なら c{条番号}、標準にあって無い条なら s{条番号}。
    touched は今回の改定案（①）で直す今の規約の条、added は今回の改定案で新しく足す条（標準の条番号）。
    今回の改定案で足す条は、②で決めることがないので判断の行に入れない（①で足すのに②にも「足すかどうか」が出て、
    二重に足すか、①の漏れと誤解する。想定ユーザーでの確認から）。"""
    touched, added = touched or set(), added or set()
    out = []
    for r in t["rows"]:
        if r["kind"] == "ほぼ同じ":
            continue
        out.append({"id": f"c{r['number']}", "type": r["kind"], "label": r["label"], "caption": r["caption"],
                    "std_label": r["std_label"], "std_caption": r["std_caption"], "amount": r["amount"],
                    "ratio": int(r["ratio"] * 100), "text": r["text"], "std_text": r.get("std_text", ""),
                    "touched": r["number"] in touched})
    for m in t["missing"]:
        if _is_added(m, added):
            continue
        out.append({"id": f"s{m['number']}", "type": "標準にない", "label": "", "caption": "", "std_label": m["label"],
                    "std_caption": m["caption"], "amount": "", "ratio": 0, "text": "", "std_text": m["text"], "touched": False})
    return out


def added_now(t: dict, added: set) -> list[dict]:
    """標準にあって今の規約にない条のうち、今回の改定案（①）で足す条。"""
    return [{"label": m["label"], "caption": m["caption"]} for m in t["missing"] if _is_added(m, added)]


def _is_added(m: dict, added: set) -> bool:
    """標準の条が、今回の改定案で足す条に当たるか（条番号か見出しが同じ）。"""
    import re

    return m["number"] in added or ("見出し:" + re.sub(r"[\s　()（）]", "", m["caption"] or "")) in added


def state(decision: dict | None) -> str:
    """later（宿題）／keep（今のまま・残す・足さない）／undecided（まだ決めていない）。今回入れる（now）は E2b ができてから。"""
    d = (decision or {}).get("d", "")
    if not d:
        return "undecided"
    if d in KEEP:
        return "keep"
    return (decision or {}).get("w") or "later"


def clean(row_type: str, d: str, w: str) -> tuple[str, str]:
    """選べない判断・時期は捨てる（画面の外から送られても）。"""
    if d not in ACTIONS.get(row_type, []):
        d = ""
    if not d or d in KEEP:
        w = ""
    else:
        w = w if w in WHEN else "later"   # 見直す判断は、今は宿題（次回以降）として記録する
    return d, w


def summary(all_rows: list[dict], decisions: dict) -> dict:
    counts = {"now": 0, "later": 0, "keep": 0, "undecided": 0}
    lists = {"now": [], "later": [], "keep": []}
    for r in all_rows:
        s = state(decisions.get(r["id"]))
        counts[s] += 1
        if s in lists:
            dec = decisions[r["id"]]
            lists[s].append({"id": r["id"], "name": r["label"] or f"標準 {r['std_label']}",
                             "caption": r["caption"] or r["std_caption"], "d": dec["d"], "m": dec.get("m", "")})
    return {"counts": counts, "lists": lists}
