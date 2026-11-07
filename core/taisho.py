"""新旧対照表を組み立てる（AI を使わない決定的な処理）。

改定案の条文と現行規約の条文を比べ、変わった部分に下線を引く。
国交省の新旧対照表と同じく、左が改定案（新）、右が現行（旧）。
"""

from __future__ import annotations

import html
import re
from difflib import SequenceMatcher

from core.draft import Draft
from core.model import Kiyaku
from core.printstyle import PRINT_CSS, page_css, toolbar
from core.sources import normalize_article_ref

DISCLAIMER = "この資料は総会提案の下書きであり、法的助言ではありません。改正区分所有法に抵触しない範囲では、内容は各管理組合が自由に決められます。"
LEGEND = "改定案の列の<mark>下線と薄い色の印</mark>は追加・変更した語句、現行の列の<del>赤の取り消し線</del>は削除・変更前の語句です。"
LEGEND_MD = "改定案の列の **太字** は追加・変更した語句、現行の列の ~~取り消し線~~ は削除・変更前の語句です。"


def _current_text(kiyaku: Kiyaku, ref: str | None) -> str:
    if not ref:
        return ""
    number = normalize_article_ref(ref)
    found = [a for a in kiyaku.articles if a.number == number]
    if not found:
        return ""
    # 選択式の規定は、すべての案を並べる
    parts = []
    for a in found:
        body = "\n".join(line for line in a.text().splitlines() if not line.startswith("（" + a.caption + "）")) if a.caption else a.text()
        parts.append((f"〔{a.variant}案〕\n" if a.variant else "") + body)
    return "\n".join(parts)


# 語句のまとまり（漢字・ひらがな・カタカナ・数字・英字の連なり、記号は1文字ずつ）
TOKEN = re.compile(r"[\u4e00-\u9fff々〆]+|[\u3041-\u309f]+|[\u30a1-\u30ffー]+|[0-9０-９]+|[A-Za-zＡ-Ｚａ-ｚ]+|\n|.", re.DOTALL)


def _tokens(s: str) -> list[str]:
    return TOKEN.findall(s)


def _marked(old: str, new: str) -> tuple[list[tuple[str, bool]], list[tuple[str, bool]]]:
    """(文字列, 変更あり) の列を、新旧それぞれについて返す。差分は語句のまとまり単位で取る。"""
    a, b = _tokens(old), _tokens(new)
    sm = SequenceMatcher(None, a, b, autojunk=False)
    old_parts, new_parts = [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            old_parts.append(("".join(a[i1:i2]), False))
            new_parts.append(("".join(b[j1:j2]), False))
        else:
            if i2 > i1:
                old_parts.append(("".join(a[i1:i2]), True))
            if j2 > j1:
                new_parts.append(("".join(b[j1:j2]), True))
    return old_parts, new_parts


def rows(draft: Draft, kiyaku) -> list[dict]:
    """kiyaku には規約本体（Kiyaku）か、規約本体と細則をまとめた Corpus を渡す。"""
    from core.corpus import Corpus

    corpus = Corpus.of(kiyaku)
    out = []
    for a in draft.amendments:
        old = _current_text(corpus.get(a.document) or corpus.main, a.before_article)
        new = "" if a.kind == "削除" else a.text
        old_parts, new_parts = _marked(old, new)
        if a.kind == "新設":
            old_parts = [("（新設）", False)]
        if a.kind == "削除":
            new_parts = [("（削る）", False)]
        out.append({"amendment": a, "old": old_parts, "new": new_parts, "old_text": old, "new_text": new})
    return out


# スマホ用：条を項ごとに分けて、改定案の項と現行の項を交互に並べる（計画C。長い条で見比べるのにスクロールが多かった）
PARA_HEAD = re.compile(r"^(?:第[0-9０-９一二三四五六七八九十百]+条(?:の[0-9０-９一二三四五六七八九十]+)*|[0-9０-９]+)[　 ]")
PARA_NO = re.compile(r"^([0-9０-９]+)[　 ]")
VARIANT_HEAD = re.compile(r"^〔[^〕]{1,12}案〕$")


def paragraphs(text: str) -> list[str]:
    """条の文を項に分ける。「2　」のような数字で始まる行と「〔甲案〕」の行が新しい項。号（一、二…）などは前の項に含める。"""
    out: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if not out or PARA_NO.match(line) or VARIANT_HEAD.match(line.strip()):
            out.append(line)
        else:
            out[-1] += "\n" + line
    return out


def _para_key(p: str) -> str:
    """見比べるときは、項の番号を除いた文で比べる（項が増えて番号だけ繰り下がった項を、同じ項として並べる）。"""
    return PARA_HEAD.sub("", p, count=1).strip()


def _para_label(p: str | None, first: bool) -> str:
    if p is None:
        return ""
    m = PARA_NO.match(p)
    if m:
        return f"第{int(m.group(1).translate(str.maketrans('０１２３４５６７８９', '0123456789')))}項"
    head = p.strip().splitlines()[0]
    if VARIANT_HEAD.match(head):
        return head
    return "第1項" if first else ""


def para_pairs(old: str, new: str) -> list[dict]:
    """項ごとの組（kind：same 変わらない／change 変わった／add 加えた／drop 削った）。"""
    a, b = paragraphs(old), paragraphs(new)
    sm = SequenceMatcher(None, [_para_key(x) for x in a], [_para_key(x) for x in b], autojunk=False)
    out = []

    def add(o, n, oi, ni):
        kind = "same" if o == n else ("add" if o is None else ("drop" if n is None else "change"))
        out.append({"kind": kind, "old": o, "new": n,
                    "old_label": _para_label(o, oi == 0), "new_label": _para_label(n, ni == 0)})

    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                add(a[i1 + k], b[j1 + k], i1 + k, j1 + k)
            continue
        olds, news = list(range(i1, i2)), list(range(j1, j2))
        for k in range(max(len(olds), len(news))):
            oi = olds[k] if k < len(olds) else None
            ni = news[k] if k < len(news) else None
            add(a[oi] if oi is not None else None, b[ni] if ni is not None else None, oi, ni)
    return out


INLINE_MIN = 0.6   # 現行の語句の6割以上が残る項は、1つの文の中で示す


def _inline_html(old: str, new: str) -> str:
    """現行の語句を赤の取り消し線、改定案の語句を色の印で、1つの文の中に示す。書き換えが多い項は空（上下に並べる）。"""
    a, b = _tokens(old), _tokens(new)
    sm = SequenceMatcher(None, a, b, autojunk=False)
    kept = sum(i2 - i1 for op, i1, i2, _j1, _j2 in sm.get_opcodes() if op == "equal")
    if not a or kept / len(a) < INLINE_MIN:
        return ""
    out = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            out.append(html.escape("".join(b[j1:j2])))
            continue
        o, n = "".join(a[i1:i2]), "".join(b[j1:j2])
        if o.strip():
            out.append(f"<del>{html.escape(o)}</del>")
        if n.strip():
            out.append(f"<mark>{html.escape(n)}</mark>")
        elif n:
            out.append(html.escape(n))
    return "".join(out).replace("\n", "<br>")


def _pairs_html(r: dict) -> str:
    a = r["amendment"]
    if a.kind in ("新設", "削除") or not r["old_text"] or not r["new_text"]:
        return ""   # 新しく加える条・削る条は、片方しかないので項に分けない（今までどおり上下に並べる）
    pairs = para_pairs(r["old_text"], r["new_text"])
    if len(paragraphs(r["new_text"])) < 2 and len(paragraphs(r["old_text"])) < 2:
        return ""   # 1つの項だけの条は、今までどおり
    out, same = [], []

    def flush():
        if not same:
            return
        names = "・".join(x["new_label"] for x in same if x["new_label"])
        body = "".join(f'<p>{html.escape(x["new"]).replace(chr(10), "<br>")}</p>' for x in same)
        out.append(f'<details class="pp-same"><summary>変わっていない項{("（" + names + "）") if names else ""}を見る</summary>{body}</details>')
        same.clear()

    for p in pairs:
        if p["kind"] == "same":
            same.append(p)
            continue
        flush()
        if p["kind"] == "change":
            label = p["new_label"] + (f'（現行の{p["old_label"]}）' if p["old_label"] and p["old_label"] != p["new_label"] else "")
            inline = _inline_html(p["old"], p["new"])
            if inline:   # 少しだけ変わった項は、1つの文の中で示す（同じ文を2回読まずに済む）
                out.append(f'<div class="pp"><div class="pp-h">{html.escape(label)}</div><div class="pp-i">{inline}</div></div>')
                continue
            o_parts, n_parts = _marked(p["old"], p["new"])
            new_html, old_html = _html_parts(n_parts, "new"), _html_parts(o_parts, "old")
        elif p["kind"] == "add":
            label = (p["new_label"] or "項") + "（加える）"
            out.append(f'<div class="pp"><div class="pp-h">{html.escape(label)}</div><div class="pp-n">{_html_parts([(p["new"], True)], "new")}</div></div>')
            continue
        else:
            label = "現行の" + (p["old_label"] or "項") + "（削る）"
            out.append(f'<div class="pp"><div class="pp-h">{html.escape(label)}</div><div class="pp-o">{_html_parts([(p["old"], True)], "old")}</div></div>')
            continue
        out.append(f'<div class="pp"><div class="pp-h">{html.escape(label)}<span class="pp-why">（書き換えが多いため、上下に並べます）</span></div>'
                   f'<div class="pp-n"><span class="pp-k">改定案</span>{new_html}</div>'
                   f'<div class="pp-o"><span class="pp-k">現行</span>{old_html}</div></div>')
    flush()
    return f'<div class="pairs"><div class="pp-lead">改定案と現行を、項ごとに見比べます。<mark>色の付いた語句</mark>が改定案で加える・変える語句、<del>赤の取り消し線</del>が現行の語句です</div>{"".join(out)}</div>'


PAIRS_CSS = """
.pairs { display: none; }
@media screen and (max-width: 720px) {
  table.taisho tr.has-pairs td.c-new .fullnew, table.taisho tr.has-pairs td.c-old { display: none !important; }
  table.taisho tr.has-pairs td.c-new::before { content: none; }
  .pairs { display: block; }
  .pp-lead { font-size: .78rem; font-weight: 700; color: var(--color-ink-3); margin: 2px 0 6px; }
  .pp { border-top: 1px solid var(--color-line); padding: 8px 0 6px; }
  .pp-h { font-size: .85rem; font-weight: 700; margin-bottom: 4px; }
  .pp-n, .pp-o { padding: 4px 8px; border-left: 3px solid var(--color-line-2); margin: 0 0 6px; }
  .pp-n { border-left-color: var(--color-primary); }
  .pp-o { color: var(--color-ink-2); background: var(--color-bg); }
  .pp-k { display: block; font-size: .72rem; font-weight: 700; color: var(--color-ink-3); }
  .pp-none { color: var(--color-ink-3); }
  .pp-i { padding: 2px 0; }
  .pp-why { font-weight: 400; color: var(--color-ink-3); font-size: .78rem; }
  .pp-same { border-top: 1px solid var(--color-line); padding: 6px 0; }
  .pp-same > summary { cursor: pointer; color: var(--color-primary); font-weight: 700; font-size: .88rem; min-height: 40px; display: flex; align-items: center; }
  .pp-same p { color: var(--color-ink-2); margin: 4px 0; }
}
@media print { .pairs { display: none !important; } }
"""


def _html_parts(parts, side: str) -> str:
    """side が "new" なら追加・変更をマーカー、"old" なら削除・変更前を取り消し線で示す。"""
    tag = "mark" if side == "new" else "del"
    return "".join(
        f"<{tag}>{html.escape(t)}</{tag}>" if changed and t.strip() else html.escape(t) for t, changed in parts
    ).replace("\n", "<br>")


NOTE_HEAD = re.compile(r"【([^】]{1,30})】")


def notes_sections(notes: str) -> list[tuple[str, str]]:
    """申し送りを【見出し】で区切る。見出しがなければ1つの節として返す。"""
    parts = NOTE_HEAD.split(notes)
    out = []
    if parts[0].strip():
        out.append(("", parts[0].strip()))
    for i in range(1, len(parts), 2):
        out.append((parts[i].strip(), parts[i + 1].strip() if i + 1 < len(parts) else ""))
    return out


def _notes_html(notes: str) -> str:
    return "".join(
        (f"<h3>{html.escape(h)}</h3>" if h else "") + f"<p>{html.escape(body).replace(chr(10), '<br>')}</p>"
        for h, body in notes_sections(notes)
    )


REQUIRED_LABEL = "法律の改正に合わせるための変更"
OPTIONAL_LABEL = "組合で選べる変更"
GUIDE = (f"「{REQUIRED_LABEL}」は、改正区分所有法に抵触して効力を失うおそれがある、または国が必ず盛り込むよう求めている変更です。"
         f"「{OPTIONAL_LABEL}」は、法律上は必須ではなく、採用するか・どう書くかを組合で決められます（変更しない、内容を変える、条文を削ることもできます）。")


def classify(a) -> dict:
    """改定を「法律の改正に合わせるための変更」と「組合で選べる変更」に分ける（改定案の論点IDから機械的に決める）。"""
    from core.topics import REQUIRED_TOPIC_IDS, TOPIC_BY_ID

    def name(t):
        topic = TOPIC_BY_ID.get(t)
        if not topic:
            return "その他の整理"
        return topic["topic"] + ("（法に抵触するか確認中）" if topic["category"] == "要確認" else "")

    required = [name(t) for t in a.finding_refs if t in REQUIRED_TOPIC_IDS]
    optional = [name(t) for t in a.finding_refs if t not in REQUIRED_TOPIC_IDS]
    if not a.finding_refs:
        optional = ["その他の整理"]
    return {"required": required, "optional": list(dict.fromkeys(optional)), "is_required": bool(required)}


def _class_html(c: dict) -> str:
    out = []
    if c["required"]:
        out.append(f'<span class="tag must">{REQUIRED_LABEL}</span><div class="topics">{html.escape("、".join(dict.fromkeys(c["required"])))}</div>')
    if c["optional"]:
        lead = "この条には、組合で選べる変更も含まれます：" if c["required"] else ""
        out.append(f'<span class="tag opt">{OPTIONAL_LABEL}</span><div class="topics">{lead}{html.escape("、".join(c["optional"]))}</div>')
    return "".join(out)


def groups(all_rows: list[dict]) -> list[tuple[str, list[dict]]]:
    """文書ごとにまとめる（規約本体を先に、細則はその後に出てきた順）。"""
    order: list[str] = []
    for r in all_rows:
        d = r["amendment"].document
        if d not in order:
            order.append(d)
    order.sort(key=lambda d: 0 if d == "規約" else 1)
    return [(d, [r for r in all_rows if r["amendment"].document == d]) for d in order]


def numbered(all_rows: list[dict]) -> list[tuple[str, list[tuple[int, dict]]]]:
    """表に出す順（文書ごと）に、行の番号（1から）を振る。画面・印刷・Word・書き込みの読み取りで同じ番号を使う。"""
    out, n = [], 0
    for document, group_rows in groups(all_rows):
        items = []
        for r in group_rows:
            n += 1
            items.append((n, r))
        out.append((document, items))
    return out


def group_heading(document: str) -> str:
    from core.corpus import Corpus

    name = "管理規約" if document == "規約" else document
    return f"{name}の改定案（総会の{Corpus.resolution(document)}）"


RESOLUTION_GUIDE = ("規約の改定は総会の特別決議（組合員総数・議決権総数の各過半数の出席、出席者の各4分の3以上の賛成）、"
                    "細則の改定は普通決議（出席者の議決権の過半数）で決めます。総会では別の議案になります。")


SKIP_LABEL = "理事会で見送り（総会には出しません）"


def is_skipped(skipped: set | None, a) -> bool:
    """理事会で見送りにした改定か（行の番号は変えずに、印を付けて示す。書き込みの写真の行番号とずれないように）。"""
    if not skipped:
        return False
    from core.explain import _ref_key, ref_name

    return _ref_key(ref_name(a)) in skipped


def edit_note(edits: dict | None, a) -> str:
    """委員会で直した条の補足（直した理由・経緯）。理由の欄に添え、AI の理由だけが残って食い違わないようにする。"""
    import re

    e = (edits or {}).get(f"{a.document or '規約'}|{a.article}") or {}
    note = str(e.get("note") or "").strip() if e.get("text") == a.text else ""
    # 前の版で「／」でつないで書き足した経緯も、日付ごとに改行で分けて見せる
    return re.sub(r"／(?=\d{1,2}月\d{1,2}日 \d{1,2}:\d{2}：)", "\n", note)


def summary_line(all_rows: list[dict], n_required: int, skipped: set | None) -> str:
    n_skip = sum(1 for r in all_rows if is_skipped(skipped, r["amendment"]))
    tail = f"。このうち{n_skip}条は理事会で見送りにしたため、総会には出しません（表には行の番号を変えずに残しています）" if n_skip else ""
    return f"改定 {len(all_rows)}条のうち、{{must}}を含む条 {n_required}条、{{opt}}だけの条 {len(all_rows) - n_required}条{tail}"


def edit_label(edits: dict | None, a) -> str:
    """委員会で直した条の印（「委員会で直した文（AI の確認前）」など）。直していない条は空。"""
    from core.editcheck import label

    return label((edits or {}).get(f"{a.document or '規約'}|{a.article}"), a.text) if edits else ""


def to_html(draft: Draft, kiyaku, title: str = "管理規約 新旧対照表（案）", ident: str = "", edits: dict | None = None,
            skipped: set | None = None) -> str:
    all_rows = rows(draft, kiyaku)
    n_required = sum(1 for r in all_rows if classify(r["amendment"])["is_required"])
    grouped = numbered(all_rows)
    sections = []
    for document, items in grouped:
        sections.append(_html_table(items, group_heading(document) if len(grouped) > 1 or document != "規約" else "", edits, skipped))
    return _html_page(draft, title, all_rows, n_required, "".join(sections), multi=len(grouped) > 1, ident=ident, skipped=skipped)


def _edit_html(text: str) -> str:
    if not text:
        return ""
    kind = "humanedit ok" if "AI 確認済み：問題なし" in text else "humanedit"
    return f'<span class="{kind}">{html.escape(text)}</span>'


def _html_table(items: list[tuple[int, dict]], heading: str, edits: dict | None = None, skipped: set | None = None) -> str:
    body = []
    for n, r in items:
        a = r["amendment"]
        c = classify(a)
        caption = f"（{html.escape(a.caption)}）<br>" if a.caption else ""
        basis = "、".join([f"区分所有法{x}" for x in a.law_basis] + [f"標準管理規約{x}" for x in a.standard_basis])
        choices = "".join(
            f"<li>〔選択〕{html.escape(c.get('point', ''))}：{html.escape(' ／ '.join(c.get('options', [])))}"
            f"{('（' + html.escape(c['note']) + '）') if c.get('note') else ''}</li>" for c in a.choices
        )
        skip = is_skipped(skipped, a)
        enote = edit_note(edits, a)
        pairs = _pairs_html(r)
        body.append(
            f'<tr class="{"row-must" if c["is_required"] else "row-opt"}{" row-skip" if skip else ""}{" has-pairs" if pairs else ""}">'
            f'<td data-label="改定案" class="c-new"><span class="rowno">行{n}</span>{"<span class=skipmark>" + SKIP_LABEL + "</span>" if skip else ""}'
            f'{_edit_html(edit_label(edits, a))}<span class="fullnew">{caption}{_html_parts(r["new"], "new")}</span>'
            f'{(caption.replace("<br>", "") + pairs) if pairs else ""}</td>'
            f"<td data-label=\"現行\" class=\"c-old\">{caption if a.kind != '新設' else ''}{_html_parts(r['old'], 'old')}</td>"
            f"<td data-label=\"区分・変更の理由・根拠\">{_class_html(c)}<b>{html.escape(a.label if hasattr(a, 'label') else a.article)}・{html.escape(a.kind)}</b><br>{html.escape(a.reason)}"
            f"{('<div class=editnote><b>委員会で直した点：</b>' + html.escape(enote) + '</div>') if enote else ''}"
            f"<br><small>根拠：{html.escape(basis)}</small>"
            f"{'<ul>' + choices + '</ul>' if choices else ''}</td>"
            "</tr>"
        )
    head = f"<h2>{html.escape(heading)}（{len(items)}条）</h2>" if heading else ""
    return (f"{head}<table class=\"taisho\"><thead><tr><th>改定案</th><th>現行</th><th>区分・変更の理由・根拠</th></tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>")


def _html_page(draft: Draft, title: str, all_rows: list[dict], n_required: int, tables: str, multi: bool, ident: str = "",
               skipped: set | None = None) -> str:
    line = summary_line(all_rows, n_required, skipped).format(must=f'<span class="tag must">{REQUIRED_LABEL}</span>',
                                                              opt=f'<span class="tag opt">{OPTIONAL_LABEL}</span>')
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{PRINT_CSS}{page_css(title, landscape=True, ident=ident)}{PAIRS_CSS}</style></head><body class="wide">
{toolbar("taisho.docx", landscape=True, back_href="./#next")}
<h1>{html.escape(title)}</h1>
<p class="note">{DISCLAIMER}</p>
<p class="legend">{LEGEND}</p>
<p class="legend">{GUIDE}</p>
<p class="legend">「行1」「行2」…は、印刷した表に書き込んだ写真から、どの行かを見分けるための番号です。</p>
<p class="summary">{line}</p>
{('<p class="legend">' + RESOLUTION_GUIDE + '</p>') if multi else ''}
{tables}
<h2>申し送り</h2>{_notes_html(draft.notes)}
</body></html>
"""


def to_markdown(draft: Draft, kiyaku: Kiyaku, title: str = "管理規約 新旧対照表（案）") -> str:
    def md(parts, side):
        return "".join(f"{side}{t.strip()}{side}" if c and t.strip() else t for t, c in parts).replace("\n", "<br>")

    lines = [f"# {title}", "", f"> {DISCLAIMER}", "", LEGEND_MD, "", GUIDE, ""]
    grouped = groups(rows(draft, kiyaku))
    if len(grouped) > 1:
        lines += [RESOLUTION_GUIDE, ""]
    for document, group_rows in grouped:
        if len(grouped) > 1 or document != "規約":
            lines += [f"## {group_heading(document)}", ""]
        lines += ["| 改定案 | 現行 | 理由・根拠 |", "| --- | --- | --- |"]
        lines += [_md_row(r, md) for r in group_rows]
        lines.append("")
    lines += ["", "## 申し送り", ""]
    for h, body in notes_sections(draft.notes):
        lines += ([f"### {h}", ""] if h else []) + [body, ""]
    return "\n".join(lines) + "\n"


def _md_row(r: dict, md) -> str:
    if True:
        a = r["amendment"]
        basis = "、".join([f"区分所有法{x}" for x in a.law_basis] + [f"標準管理規約{x}" for x in a.standard_basis])
        c = classify(a)
        label = (f"【{REQUIRED_LABEL}】" if c["is_required"] else "") + (f"【{OPTIONAL_LABEL}】" if c["optional"] else "")
        return f"| （{a.caption}）<br>{md(r['new'], '**')} | {md(r['old'], '~~')} | {label}<br>**{a.kind}** {a.reason}<br>根拠：{basis} |"
