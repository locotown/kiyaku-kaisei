"""規約ファイル（Word・テキストPDF・テキスト）から本文の行を取り出す。

紙のスキャン・写真（OCR）は MVP の対象外（docs/SPEC.md）。
"""

from __future__ import annotations

from pathlib import Path

from core.model import Kiyaku
from core.split import split_kiyaku

SUPPORTED = {".docx", ".pdf", ".txt", ".md"}


class UnsupportedFormat(ValueError):
    pass


def read_lines(path: str | Path) -> list[str]:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return _read_docx(path)
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix in {".txt", ".md"}:
        return path.read_text(encoding="utf-8").splitlines()
    raise UnsupportedFormat(f"対応していない形式です: {suffix}（対応形式: {', '.join(sorted(SUPPORTED))}）")


def _read_docx(path: Path) -> list[str]:
    import docx  # python-docx

    doc = docx.Document(str(path))
    lines: list[str] = []
    for block in doc.element.body.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = "".join(t.text or "" for t in block.iter() if t.tag.endswith("}t"))
            lines.extend(text.splitlines() or [""])
        elif tag == "tbl":
            for row in block.iter():
                if row.tag.endswith("}tr"):
                    cells = []
                    for cell in row.iterchildren():
                        if cell.tag.endswith("}tc"):
                            cells.append("".join(t.text or "" for t in cell.iter() if t.tag.endswith("}t")))
                    lines.append("　".join(c for c in cells if c))
    return lines


def _read_pdf(path: Path) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [[x.strip() for x in (page.extract_text() or "").splitlines() if x.strip()] for page in reader.pages]
    if not any(pages):
        raise UnsupportedFormat("PDFから文字を取り出せませんでした。画像だけのPDF（スキャン）は、まだ対応していません。")
    return _drop_page_furniture(pages)


def _drop_page_furniture(pages: list[list[str]], edge: int = 2) -> list[str]:
    """各ページの先頭・末尾の数行のうち、多くのページで繰り返す行（ヘッダー・フッター）を除く。

    本文中に何度も出てくる短い行（例：「ればならない。」）は消さないよう、
    判定はページの端の行に限る。
    """
    from collections import Counter

    edge_counts = Counter(line for p in pages for line in set(p[:edge] + p[-edge:]))
    threshold = max(3, len(pages) // 3)
    furniture = {line for line, c in edge_counts.items() if c >= threshold}
    lines: list[str] = []
    for p in pages:
        for i, line in enumerate(p):
            at_edge = i < edge or i >= len(p) - edge
            if at_edge and line in furniture:
                continue
            lines.append(line)
    return lines


def load_kiyaku(path: str | Path) -> Kiyaku:
    return split_kiyaku(read_lines(path))
