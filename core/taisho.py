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
        out.append({"amendment": a, "old": old_parts, "new": new_parts})
    return out


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


def to_html(draft: Draft, kiyaku, title: str = "管理規約 新旧対照表（案）", ident: str = "") -> str:
    all_rows = rows(draft, kiyaku)
    n_required = sum(1 for r in all_rows if classify(r["amendment"])["is_required"])
    grouped = numbered(all_rows)
    sections = []
    for document, items in grouped:
        sections.append(_html_table(items, group_heading(document) if len(grouped) > 1 or document != "規約" else ""))
    return _html_page(draft, title, all_rows, n_required, "".join(sections), multi=len(grouped) > 1, ident=ident)


def _html_table(items: list[tuple[int, dict]], heading: str) -> str:
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
        body.append(
            f'<tr class="{"row-must" if c["is_required"] else "row-opt"}">'
            f'<td><span class="rowno">行{n}</span>{caption}{_html_parts(r["new"], "new")}</td>'
            f"<td>{caption if a.kind != '新設' else ''}{_html_parts(r['old'], 'old')}</td>"
            f"<td>{_class_html(c)}<b>{html.escape(a.label if hasattr(a, 'label') else a.article)}・{html.escape(a.kind)}</b><br>{html.escape(a.reason)}"
            f"<br><small>根拠：{html.escape(basis)}</small>"
            f"{'<ul>' + choices + '</ul>' if choices else ''}</td>"
            "</tr>"
        )
    head = f"<h2>{html.escape(heading)}（{len(items)}条）</h2>" if heading else ""
    return (f"{head}<table><thead><tr><th>改定案</th><th>現行</th><th>区分・変更の理由・根拠</th></tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>")


def _html_page(draft: Draft, title: str, all_rows: list[dict], n_required: int, tables: str, multi: bool, ident: str = "") -> str:
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>{PRINT_CSS}{page_css(title, landscape=True, ident=ident)}</style></head><body class="wide">
{toolbar("taisho.docx", landscape=True)}
<h1>{html.escape(title)}</h1>
<p class="note">{DISCLAIMER}</p>
<p class="legend">{LEGEND}</p>
<p class="legend">{GUIDE}</p>
<p class="summary">改定 {len(all_rows)}条のうち、<span class="tag must">{REQUIRED_LABEL}</span>を含む条 {n_required}条、<span class="tag opt">{OPTIONAL_LABEL}</span>だけの条 {len(all_rows) - n_required}条</p>
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
