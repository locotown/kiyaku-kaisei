"""画面のサンプル用に、架空の規約集（evals/data/old_collection.txt）を Word 文書（.docx）にする。

Word で管理している規約集を読み込む場面を試すためのもの。見出し（文書の題名・章・条の見出し）は太字にし、
細則の改正履歴は表にする（表の読み取りも確かめるため）。中身はテキスト版と同じ。

使い方:  uv run python -m evals.build_sample_docx
"""

from __future__ import annotations

import re

from docx import Document
from docx.shared import Pt

from core.config import ROOT

SRC = ROOT / "evals/data/old_collection.txt"
OUT = ROOT / "evals/data/old_collection.docx"
HISTORY = "細則の改正履歴"


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines()
    doc = Document()
    style = doc.styles["Normal"]
    style.font.size = Pt(10.5)
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith(HISTORY):  # 改正履歴は「総会・内容」の表にする
            doc.add_paragraph(line).runs[0].bold = True
            rows = [l.split("　", 1) for l in lines[i + 1:] if l.strip()]
            table = doc.add_table(rows=1, cols=2)
            table.style = "Table Grid"
            table.rows[0].cells[0].text, table.rows[0].cells[1].text = "総会", "内容"
            for a, b in rows:
                cells = table.add_row().cells
                cells[0].text, cells[1].text = a, b
            break
        p = doc.add_paragraph(line)
        if line and p.runs and (re.match(r"^(第\S+章|（[^）]+）$|○○マンション)", line) or line == "附　則"):
            p.runs[0].bold = True
        i += 1
    doc.save(OUT)
    print(f"保存: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
