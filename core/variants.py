"""今の規約にもともとある「どちらかを選ぶ両案」（標準管理規約の（ア）（イ）など）を、理事会で選ぶ問にまとめる。

標準管理規約は、民泊を認めるか（第12条）、メールなどの電磁的方法を使うか（多くの条）のように、
組合が選ぶ前提で2通りの文を並べている。規約に両案が残ったままだと、最新の規約にも両方が残り、規約として使えない。

- 問は、案の前に置かれた注記（「〔※管理組合における電磁的方法の利用状況に応じて、次のように規定〕」）ごとに1つ。
  同じ注記の条（電磁的方法なら9条など）は、1回選べばまとめて決まる
- 改定案で書き直す条は、改定案の文が使われるので問に含めない
- 選んだ案だけを最新の規約に残す（core/consolidate.py）。AI は使わない。条の文はそのまま
- 本文の同じ行に別案がつながった形（PDF などから写したもの）は、ここでは分けられない（app/main.py の variant_articles で知らせるだけ）
"""

from __future__ import annotations

import hashlib
import re

from core.corpus import MAIN, Corpus


def _key(doc: str, note: str) -> str:
    return hashlib.sha1(f"{doc}|{note}".encode("utf-8")).hexdigest()[:10]


def _topic(note: str) -> str:
    """注記から、何を選ぶかの言葉を取り出す（「〔※管理組合における電磁的方法の利用状況に応じて、次のように規定〕」→「管理組合における電磁的方法の利用状況」）。"""
    t = re.sub(r"^〔※|〕$", "", note.strip())
    t = re.sub(r"(に応じて)?、?次のように規定$", "", t)
    return t.strip("、 ") or "どちらの案にするか"


def groups(corpus: Corpus, amended: set[tuple[str, str]] | None = None) -> list[dict]:
    """両案の問の一覧。各問：key・文書・何を選ぶか・案（記号と見出し）・対象の条（改定案で書き直す条は除く）。"""
    amended = amended or set()
    out: dict[str, dict] = {}
    for doc in corpus.names():
        k = corpus.get(doc)
        for a in k.articles if k else []:
            if not a.variant:
                continue
            note = a.note or "〔※どちらかの案を選んで規定〕"
            key = _key(doc, note)
            g = out.setdefault(key, {"key": key, "doc": doc, "note": note, "topic": _topic(note), "options": {}, "articles": [], "amended": []})
            g["options"].setdefault(a.variant, a.variant_label)
            target = g["amended"] if (doc, a.number) in amended else g["articles"]
            if a.number not in target:
                target.append(a.number)
    res = []
    for g in out.values():
        if len(g["options"]) < 2 or not g["articles"]:
            continue
        g["options"] = [{"mark": m, "label": lab} for m, lab in g["options"].items()]
        res.append(g)
    return res


def picks(gs: list[dict], choices: dict | None) -> dict[str, dict[str, str]]:
    """選んだ案を、文書ごとに {条番号: 案の記号} にする（最新の規約を組み立てるときに使う）。"""
    choices = choices or {}
    out: dict[str, dict[str, str]] = {}
    for g in gs:
        mark = choices.get(g["key"])
        if mark and mark in {o["mark"] for o in g["options"]}:
            for n in g["articles"]:
                out.setdefault(g["doc"], {})[n] = mark
    return out


def doc_label(doc: str) -> str:
    return "規約" if doc == MAIN else doc
