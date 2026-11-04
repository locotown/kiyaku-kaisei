"""検証ループ L1：標準どおりの条は、国が公表した改正後の条文を下書きにする。

現行の条が、改正前の標準管理規約の同じ番号の条と本文まで一字一句同じなら、その条の改正は
国の改正後の条文（令和7年改正 標準管理規約）がそのまま手本になる。AI に一から書かせず、
国の文を下書きとして渡し、採用した指摘の範囲に合わせて調整・確認だけをさせる。
標準に近い規約ほど、速く・安く・正確になる（docs/plans/検証ループ.md）。

条番号が標準と違う条は対象にしない（国の文の中の条の参照が、その規約では別の条を指してしまうため）。
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from core.config import ROOT
from core.findings import Finding
from core.ingest import load_kiyaku
from core.model import Article, Kiyaku
from core.sources import normalize_article_ref, standard

# 改正前の標準管理規約（令和6年版相当）。国交省の見え消し Word（data/public/mlit/r7_mikeshi_tantou.docx）から
# evals/build_r7_gold.py で取り出したもの
BEFORE = ROOT / "evals/data/r7_tantou_before.txt"
STANDARD_LIKE = 0.8  # 改正前の標準と同じ番号・同じ本文の条がこの割合以上なら「標準どおりの規約」とみなす


@lru_cache(maxsize=1)
def standard_before() -> Kiyaku:
    return load_kiyaku(BEFORE)


def body(a: Article) -> str:
    """見出しと条番号を除いた本文（全角・半角と空白の違いは無視する）。"""
    parts = []
    for p in a.paragraphs:
        parts.append(p.text)
        parts.extend(p.items)
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", "".join(parts)))


def _by_number(k: Kiyaku) -> dict[str, list[Article]]:
    out: dict[str, list[Article]] = {}
    for a in k.articles:
        out.setdefault(a.number, []).append(a)
    return out


def same_as_standard(k: Kiyaku) -> list[str]:
    """改正前の標準管理規約と、同じ番号で本文が一字一句同じ条の番号。"""
    before = _by_number(standard_before())
    return [a.number for a in k.articles if any(body(a) == body(b) for b in before.get(a.number, []))]


def standard_drafts(kiyaku: Kiyaku, findings: list[Finding]) -> dict:
    """採用した指摘の対象の条のうち、国の改正文を下書きにできる条。

    返り値：
      drafts … [{"article": "第47条", "kind": "改正"|"新設", "text": 国の改正後の条文（選択式なら両案）}]
      ratio  … 改正前の標準と同じ番号・同じ本文の条の割合
      standard_like … ratio が STANDARD_LIKE 以上か（新設の条も国の文を下書きにする）
    """
    before = _by_number(standard_before())
    after = _by_number(standard())
    same = set(same_as_standard(kiyaku))
    ratio = len(same) / max(len(before), 1)  # 選択式の両案は1条と数える
    standard_like = ratio >= STANDARD_LIKE

    drafts: list[dict] = []
    seen: set[str] = set()

    def add(number: str, kind: str) -> None:
        if number in seen or number not in after:
            return
        new = after[number]
        old = before.get(number, [])
        if old and all(any(body(n) == body(o) for o in old) for n in new):
            return  # 国の改正でこの条は変わっていない
        seen.add(number)
        drafts.append({"article": new[0].label, "kind": kind,
                       "text": "\n\n".join((f"（{n.variant}案）" if n.variant else "") + n.text() for n in new)})

    for f in findings:
        if (f.document or "規約") != "規約":
            continue
        if f.article not in ("", "規定なし"):
            number = normalize_article_ref(f.article)
            if number in same:
                add(number, "改正")
        if standard_like:  # 標準どおりの規約なら、指摘の根拠に挙げた標準の条も下書きにする（国が新設した条を含む）
            for ref in f.standard_basis:
                number = normalize_article_ref(ref)
                if number in same:
                    add(number, "改正")
                elif number not in before and number in after:
                    add(number, "新設")
    return {"drafts": drafts, "ratio": round(ratio, 3), "standard_like": standard_like, "same": len(same)}


def to_prompt(result: dict) -> str:
    """改定案を作る AI への依頼文に添える節。下書きがなければ空。"""
    if not result["drafts"]:
        return ""
    lines = [
        "## 国の改正文（下書き）",
        f"次の条は、今の規約の文が改正前の標準管理規約と一字一句同じです（規約全体では {result['same']}条が同じ）。"
        "国が公表した令和7年改正の標準管理規約の文を下書きとして使ってください。",
        "- 国の改正には、採用していない論点の変更も含まれることがあります。**採用した指摘（と理事会の判断）に当たる部分だけ**を取り入れ、"
        "それ以外の部分は今の規約の文のまま残してください（関係のない文言を変えない）",
        "- 選択式の規定（（ア）案・（イ）案）は、基本情報の電磁的方法の方針に合わせて選ぶ。未定なら〔選択〕を付けて両案を示す",
        "- 新設の条は、国の条番号のまま枝番で追加してよい（標準どおりの規約のため）",
        "- 条の参照が今の規約の条を正しく指しているかは、必ず確かめる",
        "",
    ]
    for d in result["drafts"]:
        lines += [f"### {d['article']}（{d['kind']}）", d["text"], ""]
    return "\n".join(lines)
