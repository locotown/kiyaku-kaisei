"""「○」の空欄（標準管理規約で、各マンションが数字や名前を入れる箇所）を見つける（計画D1。AI は使わない）。

標準管理規約は、役員の人数（「理事　○名」）、任期（「○年」）、理事長の報告の頻度（「○か月に1回」）、
会計年度・遅延損害金の利率・管轄裁判所・マンション名などを「○」で空けている。
標準管理規約から写した条や、ひな形のままの規約では、改定案や最新の規約に「○」が残ることがある（11/7 の確認で分かった）。
"""

from __future__ import annotations

import re

# ○（白丸）・◯（大きな丸）・〇（漢数字のゼロ）。〇は「二〇」のような漢数字の中のものは除く
BLANK = re.compile(r"(?<![一二三四五六七八九十百千〇])[○◯〇]+(?![一二三四五六七八九十百千〇])")
ART_NO = re.compile(r"^(第[0-9０-９一二三四五六七八九十百]+条(?:の[0-9０-９一二三四五六七八九十]+)*)")
BEFORE, AFTER = 7, 5   # 空欄の前後に添える文字数（どこの空欄かが分かる程度）
SHORT = 24             # これより短い行は、行ごと見せる


def snippets(text: str) -> list[str]:
    """空欄ごとに、前後の数文字を添えた抜き出し（同じものは1つに）。"""
    out: list[str] = []
    for line in text.splitlines():
        for m in BLANK.finditer(line):
            if len(line.strip()) <= SHORT:   # 号のような短い行は、行ごと見せる（「理事（理事長を含む。） ○名」）
                s = line.strip().replace("　", " ")
            else:
                s = line[max(0, m.start() - BEFORE):m.end() + AFTER].strip().replace("　", " ")
                s = ("…" if m.start() > BEFORE else "") + s + ("…" if m.end() + AFTER < len(line) else "")
            if s not in out:
                out.append(s)
    return out


def in_draft(draft: dict | None) -> list[dict]:
    """改定案の条のうち、「○」の空欄が残っている条（削る条は除く）。"""
    ams = (draft or {}).get("amendments") or []
    # 行の番号（新旧対照表・「条の文を直す」と同じ。規約を先に、細則は出てきた順。core.taisho.numbered と同じ並べ方）
    docs = sorted(dict.fromkeys(a.get("document") or "規約" for a in ams), key=lambda d: 0 if d == "規約" else 1)
    order = [i for d in docs for i, a in enumerate(ams) if (a.get("document") or "規約") == d]
    row = {i: n for n, i in enumerate(order, 1)}
    out = []
    for i, a in enumerate(ams):
        if a.get("kind") == "削除":
            continue
        found = snippets(a.get("text") or "")
        if found:
            doc = a.get("document") or "規約"
            out.append({"where": (f"{doc} " if doc != "規約" else "") + (a.get("article") or ""), "snippets": found, "n": row[i]})
    return out


def in_blocks(blocks) -> list[dict]:
    """最新の規約（consolidate のブロック）のうち、「○」の空欄が残っている条・附則・別表。今回の改定で入ったかも返す。"""
    out = []
    for b in blocks:
        if b.kind not in ("article", "appendix"):
            continue
        found = snippets("\n".join(b.lines))
        if not found:
            continue
        lines = [ln.strip() for ln in b.lines if ln.strip()]
        no = next((m.group(1) for ln in lines for m in [ART_NO.match(ln)] if m), "")   # 1行目は見出し（「（役員）」）のことが多い
        caption = lines[0] if lines and lines[0].startswith("（") and len(lines[0]) <= 30 else ""
        where = (no + caption) if no else (lines[0].split("　")[0][:12] if lines else "")
        out.append({"where": where, "snippets": found, "changed": b.changed in ("改正", "新設")})
    return out
