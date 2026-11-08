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


MAX_DOCX_UNZIPPED = 200 * 1024 * 1024   # Word の中身を展開したときの大きさの上限（小さなファイルに見せかけて膨らむものを読まない）


def _read_docx(path: Path) -> list[str]:
    import zipfile

    import docx  # python-docx

    try:
        with zipfile.ZipFile(path) as z:
            if sum(i.file_size for i in z.infolist()) > MAX_DOCX_UNZIPPED:
                raise UnsupportedFormat("Word のファイルの中身が大きすぎます")
    except zipfile.BadZipFile as e:
        raise UnsupportedFormat("Word のファイルとして読めません") from e
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
        raise UnsupportedFormat("PDFから文字を取り出せませんでした。画像だけのPDF（紙をスキャンしたもの）は、まだ対応していません。文字に起こして Word やテキストで保存してから読み込み、点検の前に「現行」の文を原本と見比べてください（数字と条番号は特に）。")
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


def load_collection(path: str | Path):
    """規約集を文書ごと（規約本体・細則・改正履歴・メモ）に分けて読み込む。"""
    from core.collection import segment

    return segment(read_lines(path))


def load_kiyaku(path: str | Path) -> Kiyaku:
    """規約本体を読み込む。規約集なら規約本体の部分だけを返す。題名が見つからなければ全体を規約として扱う。"""
    lines = read_lines(path)
    from core.collection import segment

    collection = segment(lines)
    main = collection.main
    if main and main.kiyaku and len(main.kiyaku.articles) >= 3:
        return main.kiyaku
    return split_kiyaku(lines)
