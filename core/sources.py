"""根拠として引く公開資料（改正後の標準管理規約・区分所有法）を読み込む。"""

from __future__ import annotations

import json
import re
from functools import lru_cache

from core.config import ROOT
from core.ingest import load_kiyaku
from core.model import Kiyaku

STANDARD_PDF = ROOT / "data/public/mlit/r7_hyojun_kiyaku_tantou.pdf"
LAW_JSON = ROOT / "data/public/egov/kubun_shoyu_ho_20260401.json"


@lru_cache(maxsize=1)
def standard() -> Kiyaku:
    """令和7年改正 マンション標準管理規約（単棟型）。"""
    return load_kiyaku(STANDARD_PDF)


def _text(node) -> str:
    if isinstance(node, str):
        return node
    return "".join(_text(c) for c in node.get("children", []))


def _article_lines(article: dict) -> list[str]:
    lines = []

    def walk(node, depth=0):
        if isinstance(node, str):
            return
        tag = node.get("tag")
        children = node.get("children", [])
        if tag == "ArticleCaption":
            lines.append(_text(node))
        elif tag == "Paragraph":
            num = node.get("attr", {}).get("Num", "1")
            sentence = "".join(_text(c) for c in children if isinstance(c, dict) and c.get("tag") == "ParagraphSentence")
            lines.append(("" if num == "1" else f"{num}　") + sentence)
            for c in children:
                if isinstance(c, dict) and c.get("tag") == "Item":
                    walk(c, depth + 1)
        elif tag in ("Item", "Subitem1", "Subitem2"):
            title = "".join(_text(c) for c in children if isinstance(c, dict) and c.get("tag", "").endswith("Title"))
            sentence = "".join(_text(c) for c in children if isinstance(c, dict) and c.get("tag", "").endswith("Sentence"))
            lines.append("　" * depth + f"{title}　{sentence}")
            for c in children:
                if isinstance(c, dict) and c.get("tag", "").startswith("Subitem") and not c["tag"].endswith(("Title", "Sentence")):
                    walk(c, depth + 1)
        else:
            for c in children:
                walk(c, depth)

    for c in article.get("children", []):
        walk(c)
    return lines


@lru_cache(maxsize=1)
def law() -> dict[str, str]:
    """区分所有法（2026年4月1日施行時点）の本則を、条番号（例："31", "6の2"）→本文 の辞書にする。"""
    data = json.loads(LAW_JSON.read_text(encoding="utf-8"))
    out: dict[str, str] = {}

    def find(node, tag, acc):
        if isinstance(node, dict):
            if node.get("tag") == tag:
                acc.append(node)
                return
            for c in node.get("children", []):
                find(c, tag, acc)

    mains: list = []
    find(data["law_full_text"], "MainProvision", mains)
    articles: list = []
    find(mains[0], "Article", articles)
    for a in articles:
        num = a["attr"]["Num"].replace("_", "の")
        title = "".join(_text(c) for c in a["children"] if isinstance(c, dict) and c.get("tag") == "ArticleTitle")
        out[num] = title + "\n" + "\n".join(_article_lines(a))
    return out


def normalize_article_ref(ref: str) -> str:
    """「第31条」「31」「第六条の二」「6の2」などを "31" / "6の2" に正規化する。"""
    from core.split import article_number, normalize

    ref = normalize(ref).replace(" ", "")
    item = re.match(r"^([0-9]{1,3})\.$", ref)  # 項目形式の細則（「2.」）
    if item:
        return item.group(1)
    m = re.match(r"^(?:区分所有法)?第?([0-9一二三四五六七八九十百]+)条?((?:の[0-9一二三四五六七八九十]+)*)", ref)
    if not m:
        return ref
    return article_number(m.group(1), m.group(2) or "")
