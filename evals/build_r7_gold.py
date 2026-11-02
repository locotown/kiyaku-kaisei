"""国交省「令和7年改正 改正箇所見え消し（単棟型）」から、評価用の正解データを作る。

見え消しは Word の変更履歴ではなく、書式で表されている。
  - 赤の下線        … 追加された文字
  - 赤の二重取消線  … 削除された文字
この規則で改正前（令和6年版相当）と改正後（令和7年版）の本文を段落ごとに組み立て、
条に分割して、条ごとの変更（新設・削除・変更・移動）を正解として書き出す。

出力（evals/data/）:
  r7_tantou_before.txt  … 改正前の本文。ツールへの入力に使う
  r7_tantou_after.txt   … 改正後の本文
  r7_tantou_gold.json   … 条ごとの変更と、docs/DOMAIN.md の論点・区分

出典：国土交通省「令和7年改正 改正箇所見え消し（単棟型）」
https://www.mlit.go.jp/jutakukentiku/house/content/001995687.docx を加工して作成。

使い方:  uv run python -m evals.build_r7_gold
"""

from __future__ import annotations

import json
import re
import zipfile
from difflib import SequenceMatcher
from pathlib import Path

from core.split import split_kiyaku

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/public/mlit/r7_mikeshi_tantou.docx"
OUT = ROOT / "evals/data"

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# docs/DOMAIN.md の論点表と、標準管理規約（単棟型）の条の対応。
# 区分は DOMAIN.md の「項目ごとの判定」に合わせる（必須 / 推奨 / 要確認）。
TOPICS = [
    {"id": "1-1", "topic": "特別決議を出席者の多数決に", "articles": ["47"], "category": "必須",
     "law": ["区分所有法第31条第1項", "区分所有法第17条第1項"]},
    {"id": "1-2", "topic": "特別決議の定足数", "articles": ["47"], "category": "必須",
     "law": ["区分所有法第31条第1項", "区分所有法第17条第1項"]},
    {"id": "1-3", "topic": "普通決議の定足数", "articles": ["47"], "category": "推奨", "law": []},
    {"id": "1-4", "topic": "共用部分の変更等の決議要件の緩和", "articles": ["47"], "category": "要確認",
     "law": ["区分所有法第17条第5項"]},
    {"id": "1-5", "topic": "マンション再生決議", "articles": ["47"], "category": "要確認",
     "law": ["区分所有法第62条", "区分所有法第64条の5〜第64条の8"]},
    {"id": "2-1", "topic": "招集通知に議案の要領", "articles": ["43"], "category": "必須",
     "law": ["区分所有法第35条第1項"]},
    {"id": "2-2", "topic": "緊急招集の最短期間", "articles": ["43"], "category": "必須",
     "law": ["区分所有法第35条第1項"]},
    {"id": "2-3", "topic": "多数決要件を緩和する場合の通知事項", "articles": ["43"], "category": "推奨", "law": []},
    {"id": "3", "topic": "損害賠償請求権等の代理行使", "articles": ["24の2", "24"], "category": "必須",
     "law": ["区分所有法第26条第2項"]},
    {"id": "4", "topic": "所在等不明区分所有者の総会決議からの除外", "articles": ["67の3"], "category": "推奨",
     "law": ["区分所有法第38条の2"]},
    {"id": "5", "topic": "国内管理人", "articles": ["31の3"], "category": "推奨", "law": ["区分所有法第6条の2"]},
    {"id": "6", "topic": "専有部分の保存行為の実施請求", "articles": ["23"], "category": "推奨",
     "law": ["区分所有法第6条第2項"]},
    {"id": "7", "topic": "共用部分の管理に伴う専有部分の保存行為等", "articles": ["21"], "category": "推奨",
     "law": ["区分所有法第17条第3項", "区分所有法第18条第4項"]},
    {"id": "8", "topic": "修繕積立金の使途", "articles": ["28"], "category": "推奨",
     "law": ["区分所有法第62条", "区分所有法第64条の5〜第64条の8"]},
    {"id": "9", "topic": "マンションに特化した財産管理制度", "articles": ["67の4", "67の5"], "category": "推奨",
     "law": ["区分所有法第46条の2", "区分所有法第46条の8", "区分所有法第46条の13"]},
    {"id": "10", "topic": "区分所有者の責務", "articles": ["20"], "category": "推奨", "law": ["区分所有法第5条の2"]},
    {"id": "11", "topic": "役員の欠格条項", "articles": ["36の2"], "category": "推奨", "law": []},
    {"id": "13", "topic": "防災関係業務・防火管理者", "articles": ["32", "32の2"], "category": "推奨", "law": []},
]


def _run_props(run) -> tuple[bool, bool]:
    """(削除か, 追加か) を返す。"""
    rpr = run.find(f"{W}rPr")
    if rpr is None:
        return False, False
    dstrike = rpr.find(f"{W}dstrike")
    deleted = dstrike is not None and dstrike.get(f"{W}val") not in ("0", "false")
    u = rpr.find(f"{W}u")
    inserted = u is not None and u.get(f"{W}val") not in (None, "none")
    return deleted, inserted


def read_redline(path: Path) -> tuple[list[str], list[str]]:
    """見え消しの docx から、改正前と改正後の段落のリストを返す。"""
    from xml.etree import ElementTree as ET

    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    before, after = [], []
    for p in root.iter(f"{W}p"):
        old = new = ""
        for r in p.iter(f"{W}r"):
            text = "".join((t.text or "") for t in r.iter(f"{W}t"))
            if r.find(f"{W}tab") is not None:
                text += "　"
            if not text:
                continue
            deleted, inserted = _run_props(r)
            if deleted:
                old += text
            elif inserted:
                new += text
            else:
                old += text
                new += text
        before.append(old)
        after.append(new)
    return before, after


def _body(article) -> str:
    return re.sub(r"[\s　]", "", article.text())


def compare(before, after) -> list[dict]:
    """条ごとの変更を求める。移動（番号だけ変わった条）は本文の一致で見つける。"""
    old = {a.key: a for a in before.articles}
    new = {a.key: a for a in after.articles}
    changes = []
    removed = [k for k in old if k not in new]
    added = [k for k in new if k not in old]

    moved = {}
    for nk in added:
        for ok in removed:
            if ok in moved.values():
                continue
            ratio = SequenceMatcher(None, _body(old[ok]).split("条", 1)[-1], _body(new[nk]).split("条", 1)[-1]).ratio()
            if old[ok].caption == new[nk].caption and ratio > 0.8:
                moved[nk] = ok
                break

    for nk, a in new.items():
        if nk in moved:
            ok = moved[nk]
            kind = "移動" if _body(old[ok]).split("条", 1)[-1] == _body(a).split("条", 1)[-1] else "移動・変更"
            changes.append({"key": nk, "before_key": ok, "change": kind, "caption": a.caption})
        elif nk not in old:
            changes.append({"key": nk, "before_key": None, "change": "新設", "caption": a.caption})
        elif _body(old[nk]) != _body(a):
            changes.append({"key": nk, "before_key": nk, "change": "変更", "caption": a.caption})
    for ok in removed:
        if ok not in moved.values():
            changes.append({"key": None, "before_key": ok, "change": "削除", "caption": old[ok].caption})
    return changes


def attach_topics(changes: list[dict]) -> None:
    for c in changes:
        number = (c["key"] or c["before_key"]).split("(")[0]
        c["topics"] = [t["id"] for t in TOPICS if number in t["articles"]]
        cats = {t["category"] for t in TOPICS if t["id"] in c["topics"]}
        c["category"] = "必須" if "必須" in cats else ("推奨" if "推奨" in cats else ("要確認" if cats else "その他"))


def main() -> None:
    before_lines, after_lines = read_redline(SRC)
    before = split_kiyaku(before_lines)
    after = split_kiyaku(after_lines)
    changes = compare(before, after)
    attach_topics(changes)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "r7_tantou_before.txt").write_text("\n".join(x for x in before_lines if x.strip()) + "\n", encoding="utf-8")
    (OUT / "r7_tantou_after.txt").write_text("\n".join(x for x in after_lines if x.strip()) + "\n", encoding="utf-8")
    gold = {
        "source": "国土交通省「令和7年改正 改正箇所見え消し（単棟型）」"
                  "https://www.mlit.go.jp/jutakukentiku/house/content/001995687.docx を加工して作成",
        "before_articles": len(before.articles),
        "after_articles": len(after.articles),
        "topics": TOPICS,
        "changes": changes,
    }
    (OUT / "r7_tantou_gold.json").write_text(json.dumps(gold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"改正前 {len(before.articles)}条 / 改正後 {len(after.articles)}条 / 変更 {len(changes)}件")
    for c in changes:
        print(f"  {c['change']:<5} {c['before_key'] or '-':>8} → {c['key'] or '-':<8} {c['caption']}  [{c['category']}] {','.join(c['topics'])}")


if __name__ == "__main__":
    main()
