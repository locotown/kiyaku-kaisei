"""今の規約と標準管理規約の「条の対応表」（計画E1。AI は使わない）。

方針の2段階目（標準管理規約をベースにした全部改正の準備）の材料。今の規約の条ごとに、改正後の標準管理規約のどの条に当たるかを
見出しと文で対応づけ、次に分ける。
  - ほぼ同じ … 標準管理規約とほとんど同じ文（条番号が違うだけのことも）
  - 違う … 対応する条はあるが、文が違う（違いの量：小・中・大）
  - 今の規約だけ … 標準管理規約に当たる条が見当たらない（そのマンション独自の決まりのことが多い）
  - 標準にあって今の規約にない … 標準管理規約の条で、今の規約に当たる条が見当たらない
対応づけは見出しと文の似かたによる目安。最後は人が確かめる。
"""

from __future__ import annotations

import html
import re
from difflib import SequenceMatcher

from core.model import Kiyaku

SAME = 0.95          # これ以上似ていれば「ほぼ同じ」
TEXT_MIN = 0.5       # 見出しが違っても、文がこれ以上似ていれば同じ条とみなす
CAP_MIN = 0.6        # 見出しがこれ以上似ていて、文も CAP_TEXT_MIN 以上なら同じ条とみなす
CAP_TEXT_MIN = 0.3
Z2H = str.maketrans("０１２３４５６７８９（）", "0123456789()")


def _norm(s: str) -> str:
    s = re.sub(r"〔[^〕]{1,6}案〕", "", s.translate(Z2H))   # 両案の印は比べない
    s = re.sub(r"^(?:第[0-9一二三四五六七八九十百]+条(?:の[0-9]+)*|[0-9]+|[一二三四五六七八九十]+)[\s　]", "", s, flags=re.M)
    return re.sub(r"[\s　]", "", s)


def _cap(s: str) -> str:
    return re.sub(r"[\s　()（）]", "", s or "")


def _merged(k: Kiyaku) -> list[dict]:
    """条番号ごとに1つにまとめる（（ア）（イ）の両案は1つの条として比べる）。"""
    out: dict[str, dict] = {}
    for a in k.articles:
        body = "\n".join(line for line in a.text().splitlines() if not line.startswith("（" + a.caption + "）")) if a.caption else a.text()
        e = out.setdefault(a.number, {"number": a.number, "label": a.label, "caption": a.caption, "chapter": a.chapter, "texts": []})
        e["texts"].append((f"〔{a.variant}案〕\n" if a.variant else "") + body)   # 両案は案の印を付けて並べる
    for e in out.values():
        e["text"] = "\n".join(e["texts"])
        e["norm"] = _norm(e["text"])
        e["norms"] = [_norm(x) for x in e["texts"]] + ([e["norm"]] if len(e["texts"]) > 1 else [])
    return list(out.values())


def _best(c: dict, s: dict) -> float:
    """両案（（ア）（イ））がある条は、案ごとに比べていちばん近いもので（今の規約はどちらかの案を選んでいることが多い）。"""
    return max(_ratio(x, y) for x in c["norms"] for y in s["norms"])


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def match(current: Kiyaku, standard: Kiyaku) -> dict:
    cur, std = _merged(current), _merged(standard)
    used: set[str] = set()
    pairs: dict[str, tuple[dict, float]] = {}
    by_cap: dict[str, list[dict]] = {}
    for s in std:
        by_cap.setdefault(_cap(s["caption"]), []).append(s)
    # 1. 見出しが同じ条（いちばん文が似ているもの）
    for c in cur:
        cands = [s for s in by_cap.get(_cap(c["caption"]), []) if s["number"] not in used] if c["caption"] else []
        if cands:
            best = max(cands, key=lambda s: _best(c, s))
            pairs[c["number"]] = (best, _best(c, best))
            used.add(best["number"])
    # 2. 見出しが違う条：文と見出しの似かたで探す
    for c in cur:
        if c["number"] in pairs:
            continue
        rest = [s for s in std if s["number"] not in used]
        quick = sorted(rest, key=lambda s: SequenceMatcher(None, c["norm"], s["norm"], autojunk=False).quick_ratio(), reverse=True)[:6]
        best, score = None, 0.0
        for s in quick:
            r = _best(c, s)
            cap = _ratio(_cap(c["caption"]), _cap(s["caption"])) if c["caption"] and s["caption"] else 0.0
            if (r >= TEXT_MIN or (cap >= CAP_MIN and r >= CAP_TEXT_MIN)) and r > score:
                best, score = s, r
        if best:
            pairs[c["number"]] = (best, score)
            used.add(best["number"])
    rows = []
    for c in cur:
        s, r = pairs.get(c["number"], (None, 0.0))
        if s is None:
            kind, amount = "今の規約だけ", ""
        elif r >= SAME:
            kind, amount = "ほぼ同じ", ""
        else:
            kind, amount = "違う", "小" if r >= 0.8 else ("中" if r >= 0.5 else "大")
        rows.append({"label": c["label"], "number": c["number"], "caption": c["caption"], "chapter": c["chapter"], "kind": kind,
                     "amount": amount, "ratio": round(r, 2), "std_label": s["label"] if s else "", "std_caption": s["caption"] if s else "",
                     "std_number": s["number"] if s else "", "text": c["text"], "std_text": s["text"] if s else ""})
    missing = [{"label": s["label"], "number": s["number"], "caption": s["caption"], "chapter": s["chapter"], "text": s["text"]}
               for s in std if s["number"] not in used]
    counts = {k: sum(1 for r in rows if r["kind"] == k) for k in ("ほぼ同じ", "違う", "今の規約だけ")}
    counts["標準にあって今の規約にない"] = len(missing)
    return {"rows": rows, "missing": missing, "counts": counts}


GUIDE = ("今の規約の条ごとに、改正後の標準管理規約（令和7年10月改正・単棟型）のどの条に当たるかを、見出しと文の似かたで対応づけました。"
         "標準管理規約をベースに規約を作り直す（全部改正）かを考える材料です。対応づけは目安なので、最後は人が確かめてください。"
         "「今の規約だけ」は、標準管理規約に当たる条が見当たらないもので、そのマンション独自の決まりのことが多く、作り直すときに残すか決める条です。"
         "「標準にあって今の規約にない」は、作り直すときに足すかを決める条です。")


def to_html(t: dict, title: str, ident: str = "", touched: set | None = None) -> str:
    """印刷できる対応表。touched は今回の改定案で直す条の番号（今の規約の条番号）。"""
    from core.printstyle import PRINT_CSS, page_css, toolbar
    from core.taisho import DISCLAIMER

    e = html.escape
    touched = touched or set()
    c = t["counts"]
    summary = (f"今の規約 {len(t['rows'])}か条のうち、標準管理規約とほぼ同じ {c['ほぼ同じ']}か条、違う {c['違う']}か条、"
               f"今の規約だけ {c['今の規約だけ']}か条。標準にあって今の規約にない条 {c['標準にあって今の規約にない']}か条。")

    def excerpt(s: str, n: int = 70) -> str:
        s = re.sub(r"\s+", " ", s).strip()
        return s[:n] + ("…" if len(s) > n else "")

    body = "".join(
        f"<tr class=\"{'row-must' if r['kind'] == '今の規約だけ' else ('row-opt' if r['kind'] == '違う' else '')}\">"
        f"<td data-label=\"今の規約\"><b>{e(r['label'])}</b><br><small>（{e(r['caption'])}）</small>"
        + ("<br><span class=\"tag must\">今回の改定案で直す</span>" if r["number"] in touched else "") + "</td>"
        f"<td data-label=\"標準管理規約\">{(e(r['std_label']) + '<br><small>（' + e(r['std_caption']) + '）</small>') if r['std_label'] else '—'}</td>"
        f"<td data-label=\"くらべた結果\"><b>{e(r['kind'])}</b>{('（違いの量：' + r['amount'] + '）') if r['amount'] else ''}"
        f"{('<br><small>似ている度合い ' + str(int(r['ratio'] * 100)) + '%</small>') if r['std_label'] else ''}</td>"
        f"<td data-label=\"今の規約の文（はじめの部分）\"><small>{e(excerpt(r['text']))}</small></td></tr>" for r in t["rows"])
    miss = "".join(
        f"<tr><td data-label=\"標準管理規約\"><b>{e(m['label'])}</b><br><small>（{e(m['caption'])}）</small></td>"
        f"<td data-label=\"標準管理規約の文（はじめの部分）\"><small>{e(excerpt(m['text'], 90))}</small></td></tr>" for m in t["missing"])
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<style>{PRINT_CSS}{page_css(title, landscape=True, ident=ident)}
table.taiou td {{ vertical-align: top; }}
body.wide table.taiou4 th:nth-child(1) {{ width: 17%; }} body.wide table.taiou4 th:nth-child(2) {{ width: 17%; }}
body.wide table.taiou4 th:nth-child(3) {{ width: 18%; }} body.wide table.taiou4 th:nth-child(4) {{ width: 48%; }}
body.wide table.taiou4 td:nth-child(3) {{ font-size: inherit; color: inherit; }}
</style></head><body class="wide">
{toolbar("", landscape=True, back_href="./#documents")}
<h1>{e(title)}</h1>
<p class="note">{DISCLAIMER}</p>
<p class="legend">{e(GUIDE)}</p>
<p class="summary">{e(summary)}</p>
<h2>今の規約の条（{len(t['rows'])}か条）</h2>
<table class="taisho taiou taiou4"><thead><tr><th>今の規約</th><th>標準管理規約</th><th>くらべた結果</th><th>今の規約の文（はじめの部分）</th></tr></thead><tbody>{body}</tbody></table>
<h2>標準管理規約にあって、今の規約にない条（{len(t['missing'])}か条）</h2>
{'<table class="taisho taiou"><thead><tr><th>標準管理規約</th><th>標準管理規約の文（はじめの部分）</th></tr></thead><tbody>' + miss + '</tbody></table>' if t['missing'] else '<p>ありませんでした。</p>'}
<p class="legend">この表は、文の似かたから機械的に作っています（AI は使っていません）。似ている度合いは、文字の並びがどれだけ同じかの目安です。</p>
</body></html>
"""
