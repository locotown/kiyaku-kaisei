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
from core.sources import normalize_article_ref

DISCLAIMER = "この資料は総会提案の下書きであり、法的助言ではありません。"


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
TOKEN = re.compile(r"[\u4e00-\u9fff々〆]+|[\u3041-\u309f]+|[\u30a1-\u30ffー]+|[0-9０-９]+|[A-Za-zＡ-Ｚａ-ｚ]+|\n|.", re.S)


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


def rows(draft: Draft, kiyaku: Kiyaku) -> list[dict]:
    out = []
    for a in draft.amendments:
        old = _current_text(kiyaku, a.before_article)
        new = "" if a.kind == "削除" else a.text
        old_parts, new_parts = _marked(old, new)
        if a.kind == "新設":
            old_parts = [("（新設）", False)]
        if a.kind == "削除":
            new_parts = [("（削る）", False)]
        out.append({"amendment": a, "old": old_parts, "new": new_parts})
    return out


def _html_parts(parts) -> str:
    return "".join(
        f"<u>{html.escape(t)}</u>" if changed and t.strip() else html.escape(t) for t, changed in parts
    ).replace("\n", "<br>")


def to_html(draft: Draft, kiyaku: Kiyaku, title: str = "管理規約 新旧対照表（案）") -> str:
    body = []
    for r in rows(draft, kiyaku):
        a = r["amendment"]
        caption = f"（{html.escape(a.caption)}）<br>" if a.caption else ""
        basis = "、".join([f"区分所有法{x}" for x in a.law_basis] + [f"標準管理規約{x}" for x in a.standard_basis])
        choices = "".join(
            f"<li>〔選択〕{html.escape(c.get('point', ''))}：{html.escape(' ／ '.join(c.get('options', [])))}"
            f"{('（' + html.escape(c['note']) + '）') if c.get('note') else ''}</li>" for c in a.choices
        )
        body.append(
            "<tr>"
            f"<td>{caption}{_html_parts(r['new'])}</td>"
            f"<td>{caption if a.kind != '新設' else ''}{_html_parts(r['old'])}</td>"
            f"<td><b>{html.escape(a.kind)}</b><br>{html.escape(a.reason)}"
            f"<br><small>根拠：{html.escape(basis)}</small>"
            f"{'<ul>' + choices + '</ul>' if choices else ''}</td>"
            "</tr>"
        )
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: "Hiragino Mincho ProN", "Yu Mincho", serif; margin: 24px; line-height: 1.7; color: #222; }}
h1 {{ font-size: 1.3rem; }}
.note {{ background: #fff6e0; border-left: 4px solid #e0a000; padding: 8px 12px; }}
table {{ border-collapse: collapse; width: 100%; table-layout: fixed; }}
th, td {{ border: 1px solid #888; padding: 8px; vertical-align: top; font-size: 0.92rem; word-break: break-all; }}
th {{ background: #f0f0f0; }}
td:nth-child(3) {{ font-family: sans-serif; font-size: 0.85rem; }}
u {{ text-decoration-thickness: 2px; text-underline-offset: 3px; }}
</style></head><body>
<h1>{html.escape(title)}</h1>
<p class="note">{DISCLAIMER}（下線部分が変更箇所）</p>
<table><thead><tr><th>改定案</th><th>現行</th><th>変更の理由・根拠</th></tr></thead>
<tbody>{''.join(body)}</tbody></table>
<h2>申し送り</h2><p>{html.escape(draft.notes).replace(chr(10), '<br>')}</p>
</body></html>
"""


def to_markdown(draft: Draft, kiyaku: Kiyaku, title: str = "管理規約 新旧対照表（案）") -> str:
    def md(parts):
        return "".join(f"<u>{t}</u>" if c and t.strip() else t for t, c in parts).replace("\n", "<br>")

    lines = [f"# {title}", "", f"> {DISCLAIMER}（下線部分が変更箇所）", "", "| 改定案 | 現行 | 理由・根拠 |", "| --- | --- | --- |"]
    for r in rows(draft, kiyaku):
        a = r["amendment"]
        basis = "、".join([f"区分所有法{x}" for x in a.law_basis] + [f"標準管理規約{x}" for x in a.standard_basis])
        lines.append(f"| （{a.caption}）<br>{md(r['new'])} | {md(r['old'])} | **{a.kind}** {a.reason}<br>根拠：{basis} |")
    lines += ["", "## 申し送り", "", draft.notes]
    return "\n".join(lines) + "\n"
