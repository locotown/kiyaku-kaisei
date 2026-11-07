"""読み込んだ規約が「今有効な版」かを確かめる材料（課題①②。AI は使わない）。

規約集が「本文は改正前、改正は冒頭の一覧表だけ」という形だと、そのまま読み込むと古い文で点検し、古い文に改定を重ねてしまう。
本文が改正後かどうかは機械では決められないので、確かめるのは人。ここでは、確かめる手がかりを並べる。
  - 規約集の改正の記録（改正履歴の文書・本文から外した「◆ …で改正」の注記）に出てくる条
  - 条の文の中に、作業用のメモのような文（「どちらが…」「要確認」「2026-10-07」「★」など）が混ざっていないか
"""

from __future__ import annotations

import re

from core.corpus import Corpus

VERSION_ANSWERS = {
    "はい": "はい（これまでの改正を全部反映した、今有効な内容）",
    "いいえ": "いいえ（原本の本文と、改正の一覧や議事録が分かれている）",
    "分からない": "分からない",
}
# 条の中のメモらしい言葉。規約の文には出てこない書き方だけにする（「議事録」だけでは拾わない。議事録の条があるため）
MEMO = re.compile(r"判読|転記|原文|どちらが|要確認|確認済|推測|当方|議事録で|実見|注記|\d{4}-\d{1,2}-\d{1,2}|[★◆🆕]")
CHANGE = re.compile(r"改正|改訂|新設|削除|変更")
REF = re.compile(r"第[0-9０-９一二三四五六七八九十百]+条(?:の[0-9０-９]+)?")
MAX_HISTORY = 30


def memo_lines(corpus: Corpus) -> list[dict]:
    """条の文の中に混ざった、作業用のメモのような文。"""
    out = []
    for doc, k in [("規約", corpus.main), *corpus.rules.items()]:
        for a in k.articles:
            for line in a.text().splitlines():
                m = MEMO.search(line)
                if m:
                    s = max(0, m.start() - 20)
                    out.append({"doc": doc, "article": a.label, "word": m.group(0),
                                "text": ("…" if s else "") + line[s:m.end() + 30].strip() + ("…" if m.end() + 30 < len(line) else "")})
    return out


def history(collection) -> dict:
    """規約集の改正の記録に出てくる条と、記録の行（改正履歴の文書の行と、本文から外した改正の注記）。"""
    entries, refs = [], {}
    for d in collection.documents:
        rows = []
        if d.kind == "改正履歴":
            rows = [x for x in d.lines if x.strip()]
        rows += [x for x in d.annotations if CHANGE.search(x)]
        for x in rows:
            found = list(dict.fromkeys(REF.findall(x)))
            entries.append({"doc": d.title, "kind": d.kind, "text": x.strip()[:140], "refs": found})
            for r in found:
                refs.setdefault(r, d.title)
    return {"entries": entries[:MAX_HISTORY], "count": len(entries), "articles": list(refs)}


def view(collection) -> dict:
    corpus = Corpus.from_collection(collection)
    return {"memos": memo_lines(corpus), "history": history(collection),
            "has_history": any(d.kind == "改正履歴" for d in collection.documents)}
