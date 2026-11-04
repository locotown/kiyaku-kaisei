"""画面で指摘を見せるための補助（論点名、条の見出し、根拠の条文）。

AI の出力はそのまま残し、表示のときだけ公開資料（区分所有法・標準管理規約）と
読み込んだ規約から見出しや本文を引いて添える。
"""

from __future__ import annotations

import re

from markupsafe import Markup, escape

from core.sources import law, normalize_article_ref, standard
from core.topics import TOPIC_BY_ID

# 「第67条の4」「第43条第2項」「第47条第3項第一号」など
REF = re.compile(r"第[0-9０-９一二三四五六七八九十百]+条(?:の[0-9０-９一二三四五六七八九十]+)*"
                 r"(?:第[0-9０-９一二三四五六七八九十]+項)?(?:第[0-9０-９一二三四五六七八九十]+号)?")
NO_TOPIC = "標準管理規約との違い"


def topic_title(topic_id: str) -> str:
    t = TOPIC_BY_ID.get(topic_id)
    return t["topic"] if t else NO_TOPIC


def law_caption(num: str) -> str:
    text = law().get(num, "")
    lines = text.split("\n")
    if len(lines) > 1 and lines[1].startswith("（"):
        return lines[1].strip("（）")
    return ""


def standard_caption(num: str) -> str:
    a = standard().find(num)
    return a.caption if a else ""


def _law_text(num: str) -> str:
    return law().get(num, "")


def _standard_text(num: str) -> str:
    arts = [a for a in standard().articles if a.number == num]
    return "\n\n".join((f"〔{a.variant}案〕\n" if a.variant else "") + a.text() for a in arts)


def basis(finding: dict) -> list[dict]:
    """根拠を、見出しと本文つきの一覧にする。"""
    out = []
    for ref in finding.get("law_basis", []):
        num = normalize_article_ref(ref)
        out.append({"source": "区分所有法", "kind": "law", "ref": ref, "caption": law_caption(num),
                    "text": _law_text(num)})
    for ref in finding.get("standard_basis", []):
        num = normalize_article_ref(ref)
        out.append({"source": "標準管理規約", "kind": "std", "ref": ref, "caption": standard_caption(num),
                    "text": _standard_text(num)})
    return out


def current_caption(corpus, finding: dict) -> str:
    if corpus is None or finding.get("article") in ("", "規定なし"):
        return ""
    found = corpus.find(finding.get("document"), normalize_article_ref(finding["article"]))
    return found[0].caption if found else ""


def resolution(finding: dict) -> dict:
    """この指摘の改定に必要な総会の決議。

    規約の変更は特別決議（区分所有法第31条第1項）、細則の変更は普通決議（標準管理規約第48条）。
    条文の内容ではなく、どの文書を変えるかで決まる。
    """
    doc = finding.get("document") or "規約"
    if doc != "規約":
        return {"kind": "普通", "label": "細則の変更 → 総会の普通決議"}
    if finding.get("where") == "細則で対応可":
        return {"kind": "普通", "label": "細則で対応できる → 総会の普通決議"}
    return {"kind": "特別", "label": "規約の変更 → 総会の特別決議"}


def chapter(corpus, finding: dict) -> str:
    """対象の条がある章（例：「第6章 管理組合」）。"""
    if corpus is None or finding.get("article") in ("", "規定なし"):
        return ""
    found = corpus.find(finding.get("document"), normalize_article_ref(finding["article"]))
    return " ".join(found[0].chapter.split()) if found and found[0].chapter else ""


def target(corpus, finding: dict) -> str:
    """「規約 第47条（総会の会議及び議事）」のような対象の表示。"""
    doc = finding.get("document") or "規約"
    if finding.get("article") in ("", "規定なし"):
        return f"{doc}（今の{doc}には、この点の定めがありません）"
    cap = current_caption(corpus, finding)
    return f"{doc} {finding['article']}" + (f"（{cap}）" if cap else "")


def annotate(text: str, finding: dict, corpus=None) -> Markup:
    """文中の条番号に、何の条かを小さく添える（例：第67条の4〔所有者不明専有部分管理命令〕）。

    区分所有法の条と分かるものは法の見出し、標準管理規約の根拠に挙がっている条は標準管理規約の見出し、
    それ以外は読み込んだ規約、なければ標準管理規約の見出しを使う。すでに直後に（…）があれば添えない。
    """
    std_nums = {normalize_article_ref(r) for r in finding.get("standard_basis", [])}
    doc = corpus.get(finding.get("document")) if corpus is not None else None
    out, pos = [], 0
    for m in REF.finditer(text):
        out.append(escape(text[pos:m.start()]))
        out.append(escape(m.group(0)))
        pos = m.end()
        if text[pos:pos + 1] in ("（", "("):
            continue
        num = normalize_article_ref(m.group(0))
        before = text[max(0, m.start() - 8):m.start()]
        if before.endswith("標準管理規約"):
            cap = standard_caption(num)
        elif "区分所有法" in before or before.endswith("法"):
            cap = law_caption(num)
        elif before.endswith("規約") and corpus is not None:  # 細則の指摘の中で「規約第45条」と書いた場合
            a = corpus.main.find(num)
            cap = a.caption if a else ""
        elif num in std_nums:
            cap = standard_caption(num)
        else:
            a = doc.find(num) if doc is not None else None
            cap = a.caption if a and a.caption else standard_caption(num)
        if cap:
            out.append(Markup('<span class="refcap">〔{}〕</span>').format(cap))
    out.append(escape(text[pos:]))
    return Markup("").join(out)


def _title(finding: dict, corpus) -> str:
    if finding.get("topic_id") in TOPIC_BY_ID:
        return topic_title(finding["topic_id"])
    cap = current_caption(corpus, finding)
    return f"「{cap}」の見直し" if cap else NO_TOPIC


def view(finding: dict, corpus=None) -> dict:
    return {
        "title": _title(finding, corpus),
        "target": target(corpus, finding),
        "chapter": chapter(corpus, finding),
        "resolution": resolution(finding),
        "proposal": annotate(finding.get("proposal", ""), finding, corpus),
        "issue": annotate(finding.get("issue", ""), finding, corpus),
        "basis": basis(finding),
        # 条文の読みから必須とした論点の注記（11/3 より前の点検で「推奨」として保存された指摘には出さない）
        "note": (__import__("core.topics", fromlist=["TOPIC_BY_ID"]).TOPIC_BY_ID.get(finding.get("topic_id", ""), {}).get("note", "")
                 if finding.get("category") == "必須" else ""),
    }
