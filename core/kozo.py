"""規約集の構成表（計画F1。AI は使わない）。

- 読み込んだ文書の一覧（規約・細則・改正履歴・メモ）
- 規約が「別に定める」「細則で定める」と、ほかの決まりに任せている事項ごとに、対応する細則があるか
- 細則が引いている規約の条が合っているか（「規約第16条(駐車場の使用)」なのに、規約の駐車場の条は第15条、など）

規約の見直しのときに、細則の整理（どの決まりがどの文書にあるか）を理事会で確かめるための資料。
細則の有無は、読み込んだ規約集の中で探した結果。細則が別の綴りにある・理事会の決議で決めている、ということもある。
"""

from __future__ import annotations

import html
import re

from core.corpus import MAIN, Corpus

# ほかの決まりに任せる書き方。「この規約に別に定めるもののほか」のような、規約の中を指すものは除く
DELEGATE = re.compile(r"別に[^。、]{0,8}?定め(?:る|た|ところ)|別途[^。、]{0,12}?定め(?:る|た|ところ)"
                      r"|(?:使用)?細則(?:で|において)定め(?:る|た)|細則を定め(?:る|た)")
SELF = re.compile(r"(?:この)?規約(?:に|で)別に定め")
# 任せている事項の呼び名（文の言葉から。上から順に見る）
MATTERS = [
    (r"駐車場", "駐車場の使用・使用料"),
    (r"専用使用料", "専用使用料"),
    (r"小鳥|動物|ペット|飼育", "ペット・動物の飼育"),
    (r"組合員以外の者から理事又は監事|役員.*選任方法", "外部の役員の選任方法"),
    (r"報酬|必要経費", "役員の報酬・必要経費"),
    (r"徴収日|臨時に要する費用", "管理費等の徴収日・臨時の徴収"),
    (r"窓ガラス|開口部", "窓ガラス等の改良"),
    (r"使用細則", "使用細則（建物・敷地の使い方）"),
    (r"総会及び理事会の運営|会計処理|届出事項", "総会・理事会の運営、会計処理、届出事項など"),
    (r"総会", "総会の運営"),
    (r"理事会", "理事会の運営"),
]
# 事項ごとに、名前や本文にこの言葉がある細則を「関係しそうな細則」とする
RULE_WORDS = {
    "駐車場の使用・使用料": r"駐車",
    "専用使用料": r"専用使用",
    "ペット・動物の飼育": r"ペット|動物|飼育",
    "外部の役員の選任方法": r"役員",
    "役員の報酬・必要経費": r"報酬|役員",
    "管理費等の徴収日・臨時の徴収": r"管理費|徴収",
    "使用細則（建物・敷地の使い方）": r"使用細則",
    "窓ガラス等の改良": r"窓ガラス|開口部",
    "総会の運営": r"総会",
    "総会・理事会の運営、会計処理、届出事項など": r"総会|理事会|会計|届出",
    "理事会の運営": r"理事会運営|理事会細則",
}
CITE = re.compile(r"規約第([0-9０-９]+)条(?:の([0-9０-９]+))?(?:[（(]([^）)]{1,20})[）)])?")
Z2H = str.maketrans("０１２３４５６７８９", "0123456789")


def _matter(text: str, caption: str) -> str:
    for pat, name in MATTERS:
        if re.search(pat, text):
            return name
    return caption or "（呼び名なし）"


def _para(line: str) -> str:
    m = re.match(r"^([0-9０-９]+)[　 ]", line)
    return f"第{int(m.group(1).translate(Z2H))}項" if m else ""


def delegations(corpus: Corpus) -> list[dict]:
    """規約が、ほかの決まり（細則など）に任せている事項。"""
    out = []
    for a in corpus.main.articles:
        for i, line in enumerate(a.text().splitlines()):
            if not DELEGATE.search(line) or SELF.search(line):
                continue
            para = _para(line) or ("第1項" if i <= 1 else "")
            body = re.sub(r"^(?:第[0-9０-９一二三四五六七八九十百]+条(?:の[0-9０-９]+)*|[0-9０-９]+)[　 ]", "", line.strip())
            if body.startswith("（") and body.endswith("）"):
                continue   # 見出しの行
            out.append({"article": a.label + (f"（{a.variant}案）" if a.variant else ""), "number": a.number, "para": para,
                        "caption": a.caption, "text": body, "matter": _matter(body, a.caption)})
    return out


def _same_caption(cited: str, real: str) -> bool:
    """細則が引いた見出しと規約の見出しが、同じ条を指していると言えるか。略して引く（「窓ガラス等の改良」）、
    送り仮名や「の／への」が違う（「必要箇所の立ち入り」と「必要箇所への立入り」）ものは同じとみなす。"""
    from difflib import SequenceMatcher

    a, b = re.sub(r"[　 ・、]", "", cited), re.sub(r"[　 ・、]", "", real)
    return a in b or b in a or SequenceMatcher(None, a, b).ratio() >= 0.7


def citations(corpus: Corpus) -> list[dict]:
    """細則が引いている規約の条と、それが合っているか（見出しが違えば、見出しが同じ条を探して示す）。"""
    by_no = {a.number: a for a in corpus.main.articles}
    by_cap = {a.caption: a for a in corpus.main.articles if a.caption}
    out = []
    for name, rule in corpus.rules.items():
        # 細則の前文（「管理規約第17条の規定に基づいて…」）にも根拠の条が書かれる
        text = "\n".join([*rule.preamble, *(a.text() for a in rule.articles)])
        seen = set()
        for m in CITE.finditer(text):
            no = m.group(1).translate(Z2H) + (f"-{m.group(2).translate(Z2H)}" if m.group(2) else "")
            label = f"規約第{m.group(1)}条" + (f"の{m.group(2)}" if m.group(2) else "")
            cap = m.group(3) or ""
            if (no, cap) in seen:
                continue
            seen.add((no, cap))
            art = by_no.get(no)
            row = {"rule": name, "cited": label + (f"（{cap}）" if cap else ""), "number": no, "ok": True, "note": "", "right": ""}
            if art is None:
                row.update(ok=False, note=f"規約に{label}がありません。")
            elif cap and art.caption and _same_caption(cap, art.caption):
                if cap != art.caption:
                    row["note"] = f"見出しの書き方が少し違います（規約は「{art.caption}」）。"
            elif cap and art.caption and cap != art.caption:
                right = by_cap.get(cap)
                row.update(ok=False, right=right.number if right else "", note=f"規約の{art.label}は「{art.caption}」です。"
                                           + (f"「{cap}」は{right.label}です。" if right else f"「{cap}」という見出しの条は見当たりません。"))
            out.append(row)
    return out


def build(corpus: Corpus, documents: list[dict] | None = None) -> dict:
    """構成表の中身。documents は読み込んだ文書の一覧（[{kind, title, count}]。規約集でなければ規約だけ）。"""
    cites = citations(corpus)
    cited_by: dict[str, list[str]] = {}
    misplaced: dict[str, list[dict]] = {}   # 見出しから見ると、この条を引くつもりで別の番号を書いている細則
    for c in cites:
        if c["ok"]:
            cited_by.setdefault(c["number"], []).append(c["rule"])
        elif c["right"]:
            misplaced.setdefault(c["right"], []).append(c)
    rows = []
    for d in delegations(corpus):
        strong = sorted(set(cited_by.get(d["number"], [])))
        wrong = misplaced.get(d["number"], [])
        strong += [c["rule"] for c in wrong if c["rule"] not in strong]
        word = RULE_WORDS.get(d["matter"])
        weak = [n for n, r in corpus.rules.items() if n not in strong and word
                and (re.search(word, n) or re.search(word, "\n".join(a.caption for a in r.articles)))]
        status = "ある" if strong else ("関係しそうな細則がある" if weak else "見当たらない")
        rows.append(dict(d, rules=strong, maybe=weak, status=status,
                         wrong=[f"{c['rule']}は{c['cited']}と引いています（番号のずれ）" for c in wrong]))
    if documents is None:
        documents = [{"kind": "規約", "title": "管理規約", "count": len(corpus.main.articles)}] + [
            {"kind": "細則", "title": n, "count": len(r.articles)} for n, r in corpus.rules.items()]
    return {"documents": documents, "rows": rows, "citations": cites,
            "missing": [r for r in rows if r["status"] == "見当たらない"], "bad_cites": [c for c in cites if not c["ok"]],
            "has_rules": bool(corpus.rules)}


GUIDE = ("規約は、細かい決まりを「別に定める」「細則で定める」として、細則や理事会の決議に任せることがあります。"
         "この表は、任せている事項ごとに、読み込んだ規約集の中に対応する細則があるかと、細則が引いている規約の条が合っているかを示します。"
         "細則が別の綴りにある、理事会の決議で決めている、ということもあるので、「見当たらない」は、手元の書類で確かめてください。")


def to_html(k: dict, title: str, ident: str = "") -> str:
    from core.printstyle import PRINT_CSS, page_css, toolbar
    from core.taisho import DISCLAIMER

    e = html.escape
    docs = "".join(f"<tr><td data-label=\"種類\">{e(d['kind'])}</td><td data-label=\"題名\">{e(d['title'])}</td><td data-label=\"条・項目の数\">{e(str(d.get('count') or ''))}</td></tr>"
                   for d in k["documents"])
    rows = "".join(
        f"<tr class=\"{'row-must' if r['status'] == '見当たらない' else 'row-opt'}\"><td data-label=\"事項\"><b>{e(r['matter'])}</b></td>"
        f"<td data-label=\"規約の条\">{e(r['article'])}{e(r['para'])}<br><small>（{e(r['caption'])}）</small></td><td data-label=\"規約の文\">{e(r['text'])}</td>"
        f"<td data-label=\"対応する細則\"><b>{e(r['status'])}</b>"
        + (f"<br>{e('、'.join(r['rules']))}" if r["rules"] else "")
        + (f"<br>{e('、'.join(r['maybe']))}" if r["maybe"] else "")
        + "".join(f"<br><b>ただし</b>{e(w)}" for w in r["wrong"]) + "</td></tr>" for r in k["rows"])
    cites = "".join(
        f"<tr class=\"{'row-opt' if c['ok'] else 'row-must'}\"><td data-label=\"細則\">{e(c['rule'])}</td><td data-label=\"引いている規約の条\">{e(c['cited'])}</td>"
        f"<td data-label=\"合っているか\">{('合っている' + ('（' + e(c['note']) + '）' if c['note'] else '')) if c['ok'] else '<b>ずれている</b>：' + e(c['note'])}</td></tr>" for c in k["citations"])
    summary = (f"規約がほかの決まりに任せている事項 {len(k['rows'])}件のうち、読み込んだ規約集に細則が見当たらないもの {len(k['missing'])}件。"
               + (f"細則が引いている規約の条のずれ {len(k['bad_cites'])}件。" if k["has_rules"] else "細則は読み込んでいません。"))
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<style>{PRINT_CSS}{page_css(title, landscape=True, ident=ident)}
table.kozo td, table.kozo th {{ vertical-align: top; }}
table.kozo.dl th:nth-child(1) {{ width: 18%; }} table.kozo.dl th:nth-child(2) {{ width: 14%; }} table.kozo.dl th:nth-child(3) {{ width: 42%; }}
</style></head><body class="wide">
{toolbar("", landscape=True, back_href="./#documents")}
<h1>{e(title)}</h1>
<p class="note">{DISCLAIMER}</p>
<p class="legend">{e(GUIDE)}</p>
<p class="summary">{e(summary)}</p>
<h2>読み込んだ文書（{len(k['documents'])}件）</h2>
<table class="taisho kozo"><thead><tr><th>種類</th><th>題名</th><th>条・項目の数</th></tr></thead><tbody>{docs}</tbody></table>
<h2>規約がほかの決まりに任せている事項（{len(k['rows'])}件）</h2>
{'<table class="taisho kozo dl"><thead><tr><th>事項</th><th>規約の条</th><th>規約の文</th><th>対応する細則</th></tr></thead><tbody>' + rows + '</tbody></table>' if k['rows'] else '<p>見当たりませんでした。</p>'}
<h2>細則が引いている規約の条（{len(k['citations'])}件）</h2>
{'<table class="taisho kozo"><thead><tr><th>細則</th><th>引いている規約の条</th><th>合っているか</th></tr></thead><tbody>' + cites + '</tbody></table>' if k['citations'] else '<p>' + ('細則に、規約の条を引いている箇所はありませんでした。' if k['has_rules'] else '細則は読み込んでいません。') + '</p>'}
<p class="legend">この表は、読み込んだ文書の文から機械的に作っています（AI は使っていません）。事項の呼び名は、規約の文の言葉から付けた目安です。</p>
</body></html>
"""
