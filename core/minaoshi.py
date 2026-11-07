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
                    "touched": r["number"] in touched, "fixed": r.get("fixed", False), "number": r["number"],
                    "std_number": r.get("std_number", "")})
    for m in t["missing"]:
        if _is_added(m, added):
            continue
        out.append({"id": f"s{m['number']}", "type": "標準にない", "label": "", "caption": "", "std_label": m["label"],
                    "std_caption": m["caption"], "amount": "", "ratio": 0, "text": "", "std_text": m["text"], "touched": False,
                    "fixed": False, "number": m["number"], "std_number": m["number"]})
    return out


def added_now(t: dict, added: set) -> list[dict]:
    """標準にあって今の規約にない条のうち、今回の改定案（①）で足す条。"""
    return [{"label": m["label"], "caption": m["caption"]} for m in t["missing"] if _is_added(m, added)]


def _is_added(m: dict, added: set) -> bool:
    """標準の条が、今回の改定案で足す条に当たるか（条番号か見出しが同じ）。"""
    import re

    return m["number"] in added or ("見出し:" + re.sub(r"[\s　()（）]", "", m["caption"] or "")) in added


def valid(row_type: str, decision: dict | None) -> dict | None:
    """その行で選べる判断だけを返す（対応づけを選び直して行の種類が変わったとき、前の判断を使わない）。"""
    return decision if decision and decision.get("d") in ACTIONS.get(row_type, []) else None


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
        s = state(valid(r["type"], decisions.get(r["id"])))
        counts[s] += 1
        if s in lists:
            dec = decisions[r["id"]]
            lists[s].append({"id": r["id"], "name": r["label"] or f"標準 {r['std_label']}",
                             "caption": r["caption"] or r["std_caption"], "d": dec["d"], "m": dec.get("m", ""),
                             "type": r["type"], "label": r["label"], "std_label": r["std_label"], "std_caption": r["std_caption"],
                             "text": r["text"], "std_text": r["std_text"]})
    return {"counts": counts, "lists": lists}


# ---- 宿題の検討表（計画E3-1。AI は使わない）----

def to_html(s: dict, title: str, ident: str = "", who: str = "", today: str = "") -> str:
    """次の理事会でそのまま話し合える、見直しの宿題の検討表（A4 横）。
    行ごとに今の規約と標準管理規約の文を左右に並べて違う語句に印を付け、理事会が書き込む欄を設ける。"""
    import html as h

    from core.printstyle import PRINT_CSS, page_css, toolbar
    from core.taisho import DISCLAIMER, _html_parts, _marked

    e = h.escape

    def head(i: dict) -> str:
        if i["type"] == "標準にない":
            name = f"<b>標準 {e(i['std_label'])}</b><br><small>（{e(i['std_caption'])}）</small><br><small>今の規約にない条</small>"
        else:
            name = f"<b>{e(i['label'])}</b><br><small>（{e(i['caption'])}）</small>"
            name += (f"<br><small>⇄ 標準 {e(i['std_label'])}</small>" if i["std_label"] else "<br><small>標準管理規約に当たる条なし（独自）</small>")
        memo = f"<div class=\"km\"><small>メモ：{e(i['m'])}</small></div>" if i["m"] else ""
        return f"{name}<div class=\"kd\">判断：<b>{e(i['d'])}</b></div>{memo}"

    def texts(i: dict) -> tuple[str, str]:
        cur, std = i["text"] or "", i["std_text"] or ""
        if cur and std:
            old, new = _marked(cur, std)
            return _html_parts(old, "old"), _html_parts(new, "new")
        return (e(cur).replace("\n", "<br>") or "<span class=\"muted\">（今の規約にない）</span>",
                e(std).replace("\n", "<br>") or "<span class=\"muted\">（標準管理規約に当たる条なし）</span>")

    write = ("<div class=\"kw\"><span>意見・直す方向</span><i></i><i></i><i></i></div>"
             "<div class=\"kw\"><span>担当・いつまでに</span><i></i></div>"
             "<div class=\"kw\"><span>結論</span>□ 次の改定案に入れる　□ もう少し検討　□ 今のまま</div>")
    later = s["lists"]["later"]
    rows = "".join(
        f"<tr><td data-label=\"条と判断\">{head(i)}</td>"
        f"<td data-label=\"今の規約\" class=\"kt\">{texts(i)[0]}</td>"
        f"<td data-label=\"標準管理規約\" class=\"kt\">{texts(i)[1]}</td>"
        f"<td data-label=\"理事会で書き込む\">{write}</td></tr>" for i in later)
    table = (f"<table class=\"taisho kentou\"><thead><tr><th>条と判断</th><th>今の規約</th><th>標準管理規約（令和7年10月改正）</th>"
             f"<th>理事会で書き込む</th></tr></thead><tbody>{rows}</tbody></table>") if later else "<p>宿題はありません。</p>"
    keep = s["lists"]["keep"]
    keep_html = ("<table class=\"taisho\"><thead><tr><th>条</th><th>判断</th><th>理由・経緯のメモ</th></tr></thead><tbody>"
                 + "".join(f"<tr><td data-label=\"条\"><b>{e(i['name'])}</b><br><small>（{e(i['caption'])}）</small></td>"
                           f"<td data-label=\"判断\">{e(i['d'])}</td><td data-label=\"理由・経緯のメモ\">{e(i['m'])}</td></tr>" for i in keep)
                 + "</tbody></table>") if keep else "<p>ありません。</p>"
    c = s["counts"]
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title><style>{PRINT_CSS}{page_css(title, landscape=True, ident=ident)}
body.wide table.kentou th:nth-child(1) {{ width: 16%; }} body.wide table.kentou th:nth-child(2) {{ width: 30%; }}
body.wide table.kentou th:nth-child(3) {{ width: 30%; }} body.wide table.kentou th:nth-child(4) {{ width: 24%; }}
table.kentou td {{ vertical-align: top; }} table.kentou td.kt {{ font-size: .86em; line-height: 1.6; }}
table.kentou tr {{ break-inside: avoid; }}
.kd {{ margin-top: 6px; }} .km {{ margin-top: 4px; }}
.kw {{ font-size: .82em; margin-bottom: 8px; }} .kw span {{ display: block; font-weight: 700; }}
.kw i {{ display: block; border-bottom: 1px solid #999; height: 1.7em; }}
</style></head><body class="wide">
{toolbar("", landscape=True, back_href="../minaoshi")}
<h1>{e(title)}</h1>
<p class="note">{DISCLAIMER}</p>
<p class="legend">{e(who)}{'の' if who else ''}今の規約と標準管理規約の条の対応表を見て、理事会が「見直す」と決めた条（宿題）を、次の理事会で話し合うための表です（{e(today)}時点）。
今の規約の列の<del>赤の取り消し線</del>は標準管理規約と違う語句、標準管理規約の列の<mark>色の付いた語句</mark>は今の規約と違う語句です。右の欄に、話し合った方向・担当・結論を書き込んでください。</p>
<p class="summary">宿題（次回以降に見直す） {c['later']}件・今のまま／残す／足さない {c['keep']}件・まだ決めていない {c['undecided']}件</p>
<h2>宿題（{len(later)}件）</h2>{table}
<h2>今のまま・残す・足さないと決めた条（{len(keep)}件）</h2>{keep_html}
<p class="legend">対応づけは見出しと文の似かたによる目安です（AI は使っていません）。標準管理規約の文は手本であり、そのまま入れる必要はありません。</p>
</body></html>
"""
