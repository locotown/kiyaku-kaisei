"""試験用の「長く改正していない規約」（架空）を作る。

実在の規約は使えないため、改正前の標準管理規約（令和6年版相当、evals/data/r7_tantou_before.txt）を
出発点に、次の加工を機械的に重ねて「古い規約」に近づける。架空のデータで、実在のマンションとは関係ない。

  1. 電磁的方法・WEB会議の規定を除く（選択式の規定は書面の案だけ残し、電磁的方法の項・文言も除く）
  2. 平成28年以降に加わった条を除く（暴力団員の排除、役員の欠格条項、利益相反取引、議案書の保管、
     組合員名簿等、区分所有者の所在等の探索）
  3. 住宅宿泊事業（民泊）の規定を除き、用途は「専ら住宅として使用」だけにする
  4. 組合独自の規定（架空）を加える：ペットの飼育禁止、町内会費の一括徴収、コミュニティ形成の業務
  5. 枝番を使わずに条番号を振り直し、条文中の参照（第○条）もあわせて直す
  6. 附則を古い書き方にする

出力（evals/data/）:
  old_style_kiyaku.txt … 試験用の規約（点検の入力）
  old_style_gold.json  … 必須の論点が、この規約のどの条（見出し）にあるか

使い方:  uv run python -m evals.build_old_style
"""

from __future__ import annotations

import json
import re

from core.config import ROOT
from core.model import Article, Kiyaku, Paragraph
from core.split import split_kiyaku

DATA = ROOT / "evals/data"
SRC = DATA / "r7_tantou_before.txt"

REMOVE = {"19の2", "36の2", "37の2", "49の2", "64の2", "67の2"}
WEB_PHRASES = [
    re.compile(r"[（(]WEB会議システム等を用いて開催する会議を含む。[）)]"),
    re.compile(r"[（(]WEB会議システム等を用いて会議を開催するときは、その開催方法[）)]"),
]

# 組合独自の規定（架空）。(この条の後ろに入れる, 見出し, 本文)
EXTRA_ARTICLES = [
    ("18", "ペットの飼育", [
        "区分所有者及び占有者は、専有部分及び共用部分において、犬、猫その他の動物を飼育してはならない。ただし、使用細則で定める小鳥及び観賞用の魚類については、この限りでない。",
    ]),
    ("29", "町内会費", [
        "管理組合は、町内会費を管理費とあわせて組合員から徴収し、一括して町内会に納入する。",
    ]),
]
EXTRA_ITEM_32 = "十六　地域コミュニティにも配慮した居住者間のコミュニティ形成"

# 必須の論点が、どの条（見出し）にあるか
REQUIRED_CAPTIONS = {
    "1-1": ["総会の会議及び議事"],
    "1-2": ["総会の会議及び議事"],
    "1-4": ["総会の会議及び議事"],  # 1-4〜1-6 は 11/3 に必須へ（決議要件の定めはどれも総会の議事の条にある）
    "1-5": ["総会の会議及び議事"],
    "1-6": ["総会の会議及び議事"],
    "2-1": ["招集手続"],
    "2-2": ["招集手続"],
    "3": ["損害保険", "理事長の勧告及び指示等"],
}

LAW_BEFORE = re.compile(r"(法|律|[)）]|号)$")
REF = re.compile(r"第([0-9]+)条((?:の[0-9]+)?)")
# 「区分所有法第58条第1項、第59条第1項又は第60条第1項」のように、法律の条が並ぶときの続きの部分
LIST_RUN = re.compile(r"[第0-9条項号の、又は及び並びに]*$")


def is_law_ref(text: str, start: int) -> bool:
    """start の位置の「第○条」が法律の条を指しているか（規約の条でないか）。"""
    head = text[:start]
    run = LIST_RUN.search(head)
    before = head[: run.start()] if run else head
    return bool(LAW_BEFORE.search(head[-1:] if head else "")) or bool(
        run and run.group(0) and re.search(r"第[0-9]+条", run.group(0)) and LAW_BEFORE.search(before[-1:] if before else "")
    )


def refs_removed(text: str) -> bool:
    """削除した条を参照しているか（法律の条は除く）。"""
    for m in REF.finditer(text):
        if (m.group(1) + m.group(2)) in REMOVE and not is_law_ref(text, m.start()):
            return True
    return False


def _clean(text: str) -> str:
    for p in WEB_PHRASES:
        text = p.sub("", text)
    return text


def transform(k: Kiyaku) -> list[Article]:
    out: list[Article] = []
    for a in k.articles:
        if a.number in REMOVE:
            continue
        if a.variant and a.variant != "ア":
            continue  # 選択式は（ア）の案（書面のみ／住宅宿泊事業の項は下で除く）だけ残す
        a = Article(number=a.number, caption=a.caption, chapter=a.chapter,
                    paragraphs=[Paragraph(p.num, _clean(p.text), [_clean(i) for i in p.items]) for p in a.paragraphs])
        # 削除した条を参照する項・号は除く（例：第49条の2 の準用、第67条の2 の探索）
        a.paragraphs = [p for p in a.paragraphs if not refs_removed(p.text)]
        for p in a.paragraphs:
            p.items = [x for x in p.items if not refs_removed(x)]
        # 電磁的方法だけを定める項は除き、「書面又は電磁的方法」は「書面」にする
        a.paragraphs = [p for p in a.paragraphs if not re.search(r"代えて、電磁的方法によって", p.text)]
        for i, p in enumerate(a.paragraphs, 1):
            p.num = i
            p.text = re.sub(r"又は電磁的(方法|記録)", "", p.text)
            p.items = [re.sub(r"又は電磁的(方法|記録)", "", x) for x in p.items]
        if a.number == "2":  # 電磁的方法・WEB会議の定義を除く
            a.paragraphs[0].items = [i for i in a.paragraphs[0].items
                                     if not re.match(r"^(十|十一|十二)[\s　](電磁的|WEB|電磁的記録)", i)]
        if a.number == "12":  # 民泊の項を除く
            a.paragraphs = a.paragraphs[:1]
        if a.number == "32":
            a.paragraphs[0].items.append(EXTRA_ITEM_32)
        out.append(a)
        for after, caption, texts in EXTRA_ARTICLES:
            if a.number == after:
                out.append(Article(number=f"{after}x", caption=caption, chapter=a.chapter,
                                   paragraphs=[Paragraph(i + 1, t) for i, t in enumerate(texts)]))
    return out


def renumber(articles: list[Article]) -> dict[str, str]:
    """条番号を1から振り直し、条文中の参照を直す。{元の番号: 新しい番号}"""
    mapping = {a.number: str(i + 1) for i, a in enumerate(articles)}

    def fix(text: str) -> str:
        def repl(m: re.Match) -> str:
            if is_law_ref(text, m.start()):
                return m.group(0)  # 「区分所有法第58条第1項、第59条第1項」など、法律の条は直さない
            old = m.group(1) + m.group(2)
            return f"第{mapping[old]}条" if old in mapping else m.group(0)
        return REF.sub(repl, text)

    for a in articles:
        for p in a.paragraphs:
            p.text = fix(p.text)
            p.items = [fix(i) for i in p.items]
    for a in articles:
        a.number = mapping[a.number]
    return mapping


def serialize(articles: list[Article]) -> str:
    lines = ["○○マンション管理規約（試験用・架空）", ""]
    chapter = None
    for a in articles:
        if a.chapter != chapter:
            chapter = a.chapter
            lines += ["", chapter, ""]
        lines.append(f"（{a.caption}）")
        for p in a.paragraphs:
            lines.append((f"第{a.number}条　" if p.num == 1 else f"{p.num}　") + p.text)
            lines.extend(p.items)
    lines += ["", "附　則", "（規約の発効）", "第1条　この規約は、平成12年4月1日から効力を発する。"]
    return "\n".join(lines) + "\n"


def main() -> None:
    before = split_kiyaku(SRC.read_text(encoding="utf-8").splitlines())
    articles = transform(before)
    mapping = renumber(articles)
    text = serialize(articles)
    (DATA / "old_style_kiyaku.txt").write_text(text, encoding="utf-8")

    check = split_kiyaku(text.splitlines())
    by_caption = {}
    for a in check.articles:
        by_caption.setdefault(a.caption, []).append(a.label)
    gold = {
        "source": "evals/data/r7_tantou_before.txt を evals/build_old_style.py で加工した架空の規約（実在のマンションとは関係ない）",
        "articles": len(check.articles),
        "required": {t: {"captions": caps, "articles": [x for c in caps for x in by_caption.get(c, [])]}
                     for t, caps in REQUIRED_CAPTIONS.items()},
        "mapping_from_standard": mapping,
    }
    (DATA / "old_style_gold.json").write_text(json.dumps(gold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    numbers = {a.number for a in check.articles}
    dangling = [(a.label, m.group(0)) for a in check.articles for m in REF.finditer(a.text())
                if not is_law_ref(a.text(), m.start()) and (m.group(1) + m.group(2)) not in numbers]
    if dangling:
        raise SystemExit(f"存在しない条への参照があります：{dangling}")
    print(f"試験用の規約：{len(check.articles)}条（元 {len(before.articles)}条）。存在しない条への参照：なし")
    for t, g in gold["required"].items():
        print(f"  必須 {t}: {'、'.join(g['articles'])}（{'、'.join(g['captions'])}）")


if __name__ == "__main__":
    main()
