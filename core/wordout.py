"""印刷用の資料を Word（.docx）で出す（新旧対照表・理事会の検討資料・住民向けの説明）。

委員会・理事会では、配る前に言い回しを直したり、議案書に貼り付けたりすることが多いので、
直して使える Word でも出す。画面の資料（HTML）と同じ中身・同じ順で組み立てる（AI は使わない）。

体裁：A4（新旧対照表は横）、上の欄に資料名と「総会提案の下書き」、下の欄にページ番号。
表の見出しの行は各ページの先頭にくり返す。文字は BIZ UDPゴシック（Windows に入っている UD 書体）。
"""

from __future__ import annotations

import io

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

FONT = "BIZ UDPゴシック"
INK_2 = RGBColor(0x47, 0x4C, 0x53)
INK_3 = RGBColor(0x61, 0x66, 0x6D)
MUST = RGBColor(0x9A, 0x33, 0x24)
REC = RGBColor(0x2B, 0x4F, 0x7A)
PRIMARY = RGBColor(0x24, 0x45, 0x6B)


def _font(run, size: float | None = None, bold: bool = False, color: RGBColor | None = None) -> None:
    run.font.name = FONT
    run._element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), FONT)
    if size:
        run.font.size = Pt(size)
    run.bold = bold or None
    if color is not None:
        run.font.color.rgb = color


def _field(paragraph, code: str) -> None:
    """ページ番号などのフィールド（Word が開いたときに数える）。"""
    run = paragraph.add_run()
    _font(run, 9, color=INK_2)
    for tag, attr in (("w:fldChar", {"w:fldCharType": "begin"}), ("w:instrText", None), ("w:fldChar", {"w:fldCharType": "end"})):
        el = OxmlElement(tag)
        if attr:
            for k, v in attr.items():
                el.set(qn(k), v)
        else:
            el.set(qn("xml:space"), "preserve")
            el.text = f" {code} "
        run._r.append(el)


def new_document(title: str, landscape: bool = False, ident: str = "") -> Document:
    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = FONT, Pt(10.5)
    normal.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), FONT)
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = 1.25
    sec = doc.sections[0]
    sec.page_width, sec.page_height = (Mm(297), Mm(210)) if landscape else (Mm(210), Mm(297))
    sec.orientation = WD_ORIENT.LANDSCAPE if landscape else WD_ORIENT.PORTRAIT
    sec.top_margin = sec.bottom_margin = Mm(16)
    sec.left_margin = sec.right_margin = Mm(14)
    head = sec.header.paragraphs[0]
    _font(head.add_run(" ".join(title.split())), 8, color=INK_3)
    _font(head.add_run("\t\t総会提案の下書き" + (f"　{ident}" if ident else "")), 8, color=INK_3)
    foot = sec.footer.paragraphs[0]
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _field(foot, "PAGE")
    _font(foot.add_run(" / "), 9, color=INK_2)
    _field(foot, "NUMPAGES")
    return doc


def heading(doc, text: str, level: int = 1, color: RGBColor | None = None) -> None:
    size = {0: 16, 1: 13, 2: 11.5, 3: 10.5}[level]
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt({0: 0, 1: 14, 2: 10, 3: 6}[level])
    p.paragraph_format.keep_with_next = True
    _font(p.add_run(text), size, bold=True, color=color if color is not None else (PRIMARY if level == 3 else None))


def para(doc_or_cell, text: str = "", size: float | None = None, color: RGBColor | None = None, bold: bool = False):
    p = doc_or_cell.add_paragraph()
    if text:
        _font(p.add_run(text), size, bold=bold, color=color)
    return p


def bullets(doc, items: list[str], mark: str = "・") -> None:
    for x in items:
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Mm(5)
        p.paragraph_format.first_line_indent = Mm(-3.5)
        _font(p.add_run(f"{mark}{x}"))


def note(doc, text: str) -> None:
    para(doc, text, size=9, color=INK_2)


def repeat_header(row) -> None:
    """表の見出しの行を、各ページの先頭にくり返す。"""
    tr_pr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    tr_pr.append(el)


def table(doc, headers: list[str], widths_mm: list[float]):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, h, w in zip(t.rows[0].cells, headers, widths_mm):
        cell.width = Mm(w)
        cell.paragraphs[0].text = ""
        _font(cell.paragraphs[0].add_run(h), 9, bold=True, color=INK_2)
        # 見出しの文字は、枠の上下・左右の中央に（段落の前後の余白で上に寄らないように）
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        pf = cell.paragraphs[0].paragraph_format
        pf.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf.space_before = pf.space_after = Pt(0)
    repeat_header(t.rows[0])
    return t


def add_row(t, widths_mm: list[float]):
    cells = t.add_row().cells
    for c, w in zip(cells, widths_mm):
        c.width = Mm(w)
    return cells


def save(doc) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---- 新旧対照表 ----

def taisho_docx(draft, kiyaku, title: str = "管理規約 新旧対照表（案）", ident: str = "") -> bytes:
    from core.taisho import (DISCLAIMER, GUIDE, OPTIONAL_LABEL, REQUIRED_LABEL, RESOLUTION_GUIDE, classify, group_heading,
                             notes_sections, numbered, rows)

    doc = new_document(title, landscape=True, ident=ident)
    heading(doc, title, 0)
    note(doc, DISCLAIMER)
    note(doc, "改定案の列の下線は追加・変更した語句、現行の列の取り消し線は削除・変更前の語句です。")
    note(doc, GUIDE)
    all_rows = rows(draft, kiyaku)
    n_required = sum(1 for r in all_rows if classify(r["amendment"])["is_required"])
    para(doc, f"改定 {len(all_rows)}条のうち、「{REQUIRED_LABEL}」を含む条 {n_required}条、「{OPTIONAL_LABEL}」だけの条 {len(all_rows) - n_required}条")
    grouped = numbered(all_rows)
    if len(grouped) > 1:
        note(doc, RESOLUTION_GUIDE)
    widths = [100, 90, 79]  # A4 横の本文の幅（約269mm）を 改定案・現行・理由で分ける
    for document, items in grouped:
        if len(grouped) > 1 or document != "規約":
            heading(doc, f"{group_heading(document)}（{len(items)}条）", 1)
        t = table(doc, ["改定案", "現行", "区分・変更の理由・根拠"], widths)
        for n, r in items:
            a = r["amendment"]
            c = classify(a)
            new_cell, old_cell, why_cell = add_row(t, widths)
            _font(new_cell.paragraphs[0].add_run(f"行{n}\n"), 9, bold=True, color=PRIMARY)  # 写真の書き込みから行を特定するため
            for cell, parts, side in ((new_cell, r["new"], "new"), (old_cell, r["old"], "old")):
                p = cell.paragraphs[0]
                if a.caption and not (side == "old" and a.kind == "新設"):
                    _font(p.add_run(f"（{a.caption}）\n"), 9.5)
                for text, changed in parts:
                    run = p.add_run(text)
                    _font(run, 9.5, color=MUST if (changed and side == "old" and text.strip()) else None)
                    if changed and text.strip():
                        if side == "new":
                            run.font.underline = True
                        else:
                            run.font.strike = True
            p = why_cell.paragraphs[0]
            if c["required"]:
                _font(p.add_run(f"【{REQUIRED_LABEL}】\n"), 8.5, bold=True, color=MUST)
                _font(p.add_run("、".join(dict.fromkeys(c["required"])) + "\n"), 8.5, color=INK_2)
            if c["optional"]:
                lead = "この条には、組合で選べる変更も含まれます：" if c["required"] else ""
                _font(p.add_run(f"【{OPTIONAL_LABEL}】\n"), 8.5, bold=True, color=REC)
                _font(p.add_run(lead + "、".join(c["optional"]) + "\n"), 8.5, color=INK_2)
            label = a.label if hasattr(a, "label") else a.article
            _font(p.add_run(f"{label}・{a.kind}\n"), 9, bold=True)
            _font(p.add_run(a.reason), 9)
            basis = "、".join([f"区分所有法{x}" for x in a.law_basis] + [f"標準管理規約{x}" for x in a.standard_basis])
            if basis:
                _font(why_cell.add_paragraph().add_run(f"根拠：{basis}"), 8, color=INK_3)
            for ch in a.choices:
                text = f"〔選択〕{ch.get('point', '')}：{' ／ '.join(ch.get('options', []))}" + (f"（{ch['note']}）" if ch.get("note") else "")
                _font(why_cell.add_paragraph().add_run(text), 8.5)
    heading(doc, "申し送り", 1)
    for h, body in notes_sections(draft.notes):
        if h:
            heading(doc, h, 2)
        for line in body.split("\n"):
            if line.strip():
                para(doc, line)
    return save(doc)


# ---- 理事会の検討資料 ----

def board_docx(paper, decisions: dict | None = None, name: str = "", points: dict | None = None, ident: str = "") -> bytes:
    from core.board import DECISIONS, DISCLAIMER, TIER_TASK, TIERS

    decisions, points = decisions or {}, points or {}
    doc = new_document(paper.title, ident=ident)
    heading(doc, paper.title, 0)
    if name:
        note(doc, name)
    para(doc, paper.intro)
    current = None
    for i, it in enumerate(paper.items):
        if it.tier != current:
            current = it.tier
            n = TIERS.index(it.tier)
            task, guide = TIER_TASK[it.tier]
            heading(doc, f"{'①②③'[n]} {it.tier}：{task}", 1, color=(MUST, REC, INK_2)[n])
            note(doc, guide)
        d = decisions.get(str(i), {})
        heading(doc, f"{i + 1}. {it.title}", 2)
        note(doc, f"関係する条：{'、'.join(it.articles)}")
        para(doc, it.summary)
        heading(doc, f"{TIER_TASK[it.tier][0].replace('する', '')}のポイント", 3)
        bullets(doc, it.points)
        if it.options:
            heading(doc, "選べる案", 3)
            bullets(doc, it.options)
        pts = points.get(i, [])
        if pts:
            heading(doc, "選ぶ必要があります（〔選択〕）", 3, color=MUST)
            picked = d.get("picked") or {}
            for j, p in enumerate(pts):
                para(doc, f"{p['ref']}（{p['caption']}）：{p['point']}", bold=True)
                mine = picked.get(str(j), "")
                opts = [f"{'☑' if o == mine else '□'} {o}" for o in p["options"]] or [f"☑ {mine}" if mine else "□ ＿＿＿＿＿＿＿＿"]
                bullets(doc, opts, mark="")
                if p.get("note"):
                    note(doc, p["note"])
        if it.questions:
            heading(doc, "想定される質問", 3)
            bullets(doc, it.questions)
        para(doc, "判断：" + "　".join(f"□ {c}" for c in DECISIONS[it.tier]) + "　メモ：＿＿＿＿＿＿＿＿＿＿＿＿＿＿")
        if d.get("decision"):
            text = f"理事会の判断：{d['decision']}" + (f"／選んだ案：{d['choice']}" if d.get("choice") else "") + (f"／メモ：{d['note']}" if d.get("note") else "")
            para(doc, text, color=RGBColor(0x2D, 0x6A, 0x4F))
    if paper.notes:
        heading(doc, "参考：今回の改定案に含まれていない点", 1)
        bullets(doc, paper.notes)
    heading(doc, "このあとの流れ", 1)
    para(doc, paper.next_steps)
    note(doc, f"{DISCLAIMER}　改定案の条文そのものは「新旧対照表」を見てください。")
    return save(doc)


# ---- 住民向けの説明 ----

def explain_docx(ex, name: str = "", draft=None, ident: str = "") -> bytes:
    from core.explain import DISCLAIMER, TIER_GUIDE, TIERS, coverage

    doc = new_document(ex.title, ident=ident)
    heading(doc, ex.title, 0)
    if name:
        note(doc, name)

    def paras(text: str) -> None:
        for x in text.split("\n"):
            if x.strip():
                para(doc, x)

    paras(ex.intro)
    current = None
    for i, it in enumerate(ex.items, 1):
        if it.tier != current:
            current = it.tier
            n = TIERS.index(it.tier)
            heading(doc, f"{'①②③'[n]} {it.tier}", 1, color=(MUST, REC, INK_2)[n])
            note(doc, TIER_GUIDE[it.tier])
        heading(doc, f"{i}. {it.title}", 2)
        note(doc, ("【法律の改正に合わせるための変更】" if it.required else "【組合で選べる変更】") + f"　関係する条：{'、'.join(it.articles)}")
        for h, body in (("何が変わるのか", it.what), ("なぜ変えるのか", it.why), ("暮らしや手続きへの影響", it.impact)):
            heading(doc, h, 3)
            paras(body)
    heading(doc, "皆さんのご意見を伺いたい点", 1)
    bullets(doc, ex.choices)
    heading(doc, "総会での決め方", 1)
    paras(ex.resolution)
    paras(ex.closing)
    if draft is not None:
        from core.taisho import classify

        cov = coverage(ex, draft)
        heading(doc, f"付録：変更する条の一覧（{len(cov['rows'])}条）", 1)
        widths = [24, 46, 16, 32, 20, 44]
        t = table(doc, ["条", "見出し", "種類", "区分", "決議", "説明の項目"], widths)
        for r, a in zip(cov["rows"], draft.amendments):
            vals = [r["article"], r["caption"], r["kind"], "法律の改正に合わせる" if classify(a)["is_required"] else "組合で選べる",
                    "特別決議" if a.document == "規約" else "普通決議", "、".join(str(x) for x in r["items"]) or "本文では取り上げていません"]
            for cell, v in zip(add_row(t, widths), vals):
                _font(cell.paragraphs[0].add_run(v), 9)
    note(doc, DISCLAIMER)
    return save(doc)
