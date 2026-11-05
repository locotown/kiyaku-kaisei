"""総会で可決した改定を反映した、最新の規約（細則）の全文を組み立てる。

AI は使わない。読み込んだ今の規約（条・項・号・章・附則）に、最終の改定案（改正・新設・削除）を機械的に重ねる。
  - 改正した条は差し替え、新設した条は条番号の順の位置に入れる（章は直前の条と同じ）
  - 削除した条は「第○条　削除」と残す（条番号を変えないための一般的な書き方）
  - 附則に、今回の改正の施行日を足す
書式（字下げ・表・別表のレイアウト）は再現しない。文字だけを正確に組み立てる。
"""

from __future__ import annotations

import html
import io
import re
from dataclasses import dataclass, field
from datetime import date

from core.draft import Amendment
from core.model import Article, Kiyaku
from core.printstyle import PRINT_CSS, page_css, toolbar
from core.sources import normalize_article_ref


@dataclass
class Block:
    kind: str  # title / chapter / article / appendix
    lines: list[str] = field(default_factory=list)
    changed: str = ""  # "" / 改正 / 新設 / 削除 / 附則


def wareki(d: date) -> str:
    """令和の日付（例：令和8年5月24日）。"""
    if d >= date(2019, 5, 1):
        y = d.year - 2018
        return f"令和{'元' if y == 1 else y}年{d.month}月{d.day}日"
    return f"{d.year}年{d.month}月{d.day}日"


def _key(number: str) -> tuple[int, ...]:
    """条番号の並び順（"69の2" → (69, 2)）。"""
    return tuple(int(x) if x.isdigit() else 0 for x in number.split("の"))


def _label(number: str, style: str) -> str:
    if style == "項目":
        return f"{number}."
    head, *rest = number.split("の")
    return f"第{head}条" + "".join(f"の{r}" for r in rest)


def _article_lines(a: Article) -> list[str]:
    if a.style == "項目":
        lines = [f"{a.label} {a.caption}".rstrip()]
        for p in a.paragraphs:
            if p.text.strip():
                lines.append(p.text)
            lines.extend(p.items)
        return lines
    lines = [f"〔{a.variant}案〕"] if a.variant else []
    return lines + a.text().splitlines()


def _amendment_lines(am: Amendment, style: str) -> list[str]:
    number = normalize_article_ref(am.article)
    label = _label(number, style)
    body = [line for line in am.text.splitlines() if line.strip()]
    if style == "項目":
        first = re.sub(rf"^{re.escape(label)}\s*", "", body[0]) if body else ""
        return [f"{label} {am.caption}".rstrip()] + ([first] if first else []) + body[1:]
    return ([f"（{am.caption}）"] if am.caption else []) + body


def consolidate(kiyaku: Kiyaku, amendments: list[Amendment], title: str,
                effective: date | None = None, meeting: str = "") -> list[Block]:
    """今の規約に改定を重ねて、最新の全文をブロックの並びにする。"""
    style = kiyaku.articles[0].style if kiyaku.articles else "条"
    by_num = {normalize_article_ref(a.article): a for a in amendments}
    rows: list[tuple[tuple[int, ...], int, str, list[str], str]] = []  # (並び順, 元の順, 章, 行, 変更)
    seen: set[str] = set()
    for order, art in enumerate(kiyaku.articles):
        if art.number in seen:  # 選択式の規定（ア・イ）は、改定があれば1つにまとめて差し替える
            if art.number in by_num:
                continue
        seen.add(art.number)
        am = by_num.get(art.number)
        if am is None:
            rows.append((_key(art.number), order, art.chapter, _article_lines(art), ""))
        elif am.kind == "削除":
            rows.append((_key(art.number), order, art.chapter, [f"{_label(art.number, style)}　削除"], "削除"))
        else:
            rows.append((_key(art.number), order, art.chapter, _amendment_lines(am, style), "改正"))
    for num, am in by_num.items():
        if am.kind == "新設" and num not in seen:
            rows.append((_key(num), 10**6, "", _amendment_lines(am, style), "新設"))
    rows.sort(key=lambda r: (r[0], r[1]))

    blocks = [Block("title", [title])]
    for line in kiyaku.preamble:
        if line.strip():
            blocks.append(Block("appendix", [line]))
    chapter = None
    for _, _, ch, lines, changed in rows:
        ch = ch or chapter or ""  # 新設の条は直前の条と同じ章
        if ch and ch != chapter:
            blocks.append(Block("chapter", [ch]))
        chapter = ch
        blocks.append(Block("article", lines, changed))
    if kiyaku.appendix:
        blocks.append(Block("appendix", [line for line in kiyaku.appendix if line.strip()]))
    if effective:
        what = "細則" if "細則" in title else "規約"
        head = f"附　則（{wareki(effective)}{('　' + meeting) if meeting else ''}改正）"
        blocks.append(Block("appendix", [head, "（施行期日）", f"この{what}の改正は、{wareki(effective)}から施行する。"], "附則"))
    return blocks


def to_text(blocks: list[Block]) -> str:
    out = []
    for b in blocks:
        out.extend(b.lines)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def to_docx(blocks: list[Block], ident: str = "") -> bytes:
    """Word 文書にする（見出しは太字、条の見出しは段落を分ける）。体裁はほかの資料と同じ（資料名・ページ番号・書体）。"""
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    from core.wordout import new_document

    doc = new_document(blocks[0].lines[0] if blocks else "最新の規約", ident=ident)
    for b in blocks:
        if b.kind == "title":
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(b.lines[0])
            r.bold, r.font.size = True, Pt(14)
            continue
        if b.kind == "chapter":
            p = doc.add_paragraph()
            p.add_run(b.lines[0]).bold = True
            continue
        for i, line in enumerate(b.lines):
            p = doc.add_paragraph(line)
            if i == 0 and (line.startswith("（") or line.startswith("附")):
                p.runs[0].bold = line.startswith("附")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def to_html(blocks: list[Block], note: str = "", word_href: str = "", ident: str = "") -> str:
    """画面で確認する用。変更した条に色を付ける。"""
    labels = {"改正": "改正", "新設": "新設", "削除": "削除", "附則": "今回追加"}
    parts = []
    for b in blocks:
        if b.kind == "title":
            parts.append(f"<h1>{html.escape(b.lines[0])}</h1>")
        elif b.kind == "chapter":
            parts.append(f"<h2>{html.escape(b.lines[0])}</h2>")
        else:
            tag = f'<span class="tag t-{b.changed}">{labels[b.changed]}</span>' if b.changed else ""
            body = "<br>".join(html.escape(x) for x in b.lines)
            parts.append(f'<div class="art{" ch changed" if b.changed else ""}">{tag}{body}</div>')
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(blocks[0].lines[0] if blocks else "最新の規約")}</title>
<style>{PRINT_CSS}{page_css(blocks[0].lines[0] if blocks else "最新の規約", ident=ident)}</style></head><body class="final">
{toolbar(word_href, back_href="../../")}
{f'<p class="note">{html.escape(note)}</p>' if note else ''}
{''.join(parts)}
</body></html>
"""
