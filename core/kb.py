"""知識ベース（正規版）の入口。

正規版では、法令・標準管理規約・そのコメントを、条ごとに整理した知識ベース（選ぶ点・判断の目安・法の条とのつながり。
原文の引用付き）を裏で使う。知識ベースの中身は公開リポジトリに置かない（非公開）。
β版（このリポジトリだけで動かす形）には知識ベースがないので、ここは何も返さず、今までどおり動く。

置き場所：環境変数 KIYAKU_KB（ファイルのパス）。なければ private/kb/kb_tantou.json（コミットしない場所）を見る。
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from core.sources import normalize_article_ref

ROOT = Path(__file__).resolve().parent.parent
DEFAULT = ROOT / "private" / "kb" / "kb_tantou.json"
MAX_COMMENT = 1500   # コメントが長い条は、先頭と選ぶ点の文に絞る（AI に渡す量を抑える）


def path() -> Path | None:
    if os.environ.get("KIYAKU_KB_OFF"):
        return None
    p = Path(os.environ.get("KIYAKU_KB") or DEFAULT)
    return p if p.exists() else None


@lru_cache(maxsize=2)
def _load(p: str) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def load() -> dict | None:
    p = path()
    return _load(str(p)) if p else None


def available() -> bool:
    return load() is not None


def standard_extra(ref: str) -> str:
    """標準管理規約の条に添える、コメント・組合が選ぶ点・判断の目安（知識ベースがなければ空）。"""
    kb = load()
    if not kb:
        return ""
    r = (kb.get("standard") or {}).get(normalize_article_ref(ref))
    if not r:
        return ""
    parts = []
    c = r.get("comment")
    if c and c.get("text"):
        t = c["text"]
        parts.append(f"《コメント（{c.get('heading', '')}）》\n" + (t if len(t) <= MAX_COMMENT else t[:MAX_COMMENT] + "…（以下略）"))
    choices = [x for x in r.get("choices", []) if x.get("kind") != "コメントの選択肢"]
    if choices:
        parts.append("《組合が選ぶ点（標準管理規約が断定せず、各マンションで決める点）》\n" + "\n".join(
            f"- {x['kind']}：{x.get('topic', '')}" + (f"（{' ／ '.join(x['options'])}）" if x.get("options") else "")
            + (f"　原文：{x['quote']}" if x.get("quote") else "") for x in choices))
    for g in r.get("guides", []):
        parts.append(f"《判断の目安：{g['topic']}》\n案：{' ／ '.join(g['options'])}\n{g['guide']}\n根拠（原文）：" + " ／ ".join(g["quotes"]))
    return ("\n\n".join(parts)) if parts else ""


def version() -> str:
    """作業に記録する知識ベースの版（なければ空）。"""
    kb = load()
    if not kb:
        return ""
    meta = kb.get("meta") or {}
    return f"{meta.get('name', '')}／" + "・".join(f"{s.get('file', '').rsplit('/', 1)[-1]}@{s.get('sha', '')}" for s in meta.get("sources", []))
