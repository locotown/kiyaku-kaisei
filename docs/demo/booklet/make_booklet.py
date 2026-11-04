"""手元の撮影に使う、架空の規約集の冊子（A5 の PDF）を作る。

中身はサンプル evals/data/old_collection.txt（架空の規約集）の規約本体。マンション名だけ「さくら台マンション」に置き換える。
使い方: uv run python -m docs.demo.booklet.make_booklet は使えないので、PYTHONPATH=. uv run python docs/demo/booklet/make_booklet.py && node docs/demo/booklet/to_pdf.js
"""

import html
import re
from pathlib import Path

from core.corpus import Corpus
from core.ingest import load_collection

ROOT = Path(__file__).resolve().parents[3]
NAME = "さくら台マンション"
corpus = Corpus.from_collection(load_collection(ROOT / "evals/data/old_collection.txt"))
arts = []
for a in corpus.main.articles:
    lines = a.text().replace("○○マンション", NAME).splitlines()
    head, rest = lines[0], lines[1:]
    num, _, body = head.partition("　")
    arts.append(f'<div class="art"><div class="cap">{html.escape((re.search(r"（[^）]*）", a.label) or [""])[0])}</div>'
                f'<p><b>{html.escape(num)}</b>　{html.escape(body)}</p>'
                + "".join(f"<p class=\"para\">{html.escape(x)}</p>" for x in rest if x.strip()) + "</div>")
doc = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<style>
@font-face {{ font-family: "NSJP"; font-weight: 400; src: url("https://cdn.jsdelivr.net/npm/@fontsource/noto-sans-jp@5.0.19/files/noto-sans-jp-japanese-400-normal.woff2"); }}
@font-face {{ font-family: "NSJP"; font-weight: 700; src: url("https://cdn.jsdelivr.net/npm/@fontsource/noto-sans-jp@5.0.19/files/noto-sans-jp-japanese-700-normal.woff2"); }}
@page {{ size: A5; margin: 16mm 14mm; }}
body {{ font-family: "NSJP", sans-serif; font-size: 9.5pt; line-height: 1.75; color: #1f1f1f; }}
.cover {{ height: 160mm; display: flex; flex-direction: column; justify-content: center; align-items: center; page-break-after: always; text-align: center; }}
.cover h1 {{ font-size: 24pt; letter-spacing: .15em; margin: 0; }}
.cover .org {{ font-size: 13pt; margin-top: 18mm; letter-spacing: .1em; }}
.cover .note {{ font-size: 8pt; color: #777; margin-top: 40mm; }}
.art {{ margin: 0 0 3mm; break-inside: avoid; }} .cap {{ font-weight: 700; font-size: 9pt; }}
p {{ margin: 0; text-indent: -1em; padding-left: 1em; }} .para {{ text-indent: -1em; padding-left: 1em; }}
</style></head><body>
<div class="cover"><h1>管理規約</h1><div class="org">{NAME}管理組合</div>
<div class="note">（架空の規約です。デモ動画の撮影用）</div></div>
{''.join(arts)}
</body></html>"""
(Path(__file__).parent / "booklet.html").write_text(doc, encoding="utf-8")
print("条", len(arts))
