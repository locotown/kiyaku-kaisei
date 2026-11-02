"""規約の本文（行のリスト）を、条・項・号に分割する。

想定する書き方（標準管理規約と、それに準拠した多くの規約）:
  （目的）                      ← 見出し（条の前の行）
  第１条　この規約は、…          ← 条の始まり（第1項）
  ２　前項の…                   ← 第2項以降
  一　…                         ← 号
  イ　… /（１）…                 ← 号の細分（直前の号に含める）
見出しが条番号と同じ行にある書き方（「第1条（目的）　本文」）にも対応する。

PDF から取り出した文章のように1文が途中で改行されている場合は、
上のどの形にも当たらない行を直前の要素の続きとしてつなげる。
"""

from __future__ import annotations

import re
import unicodedata

from core.model import Article, Kiyaku, Paragraph

KANJI_NUM = {"〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}

SP = r"[\s　]"
RE_CHAPTER = re.compile(rf"^第[0-9一二三四五六七八九十]+章(?:{SP}|$)")
RE_SECTION = re.compile(rf"^第[0-9一二三四五六七八九十]+節(?:{SP}|$)")
RE_ARTICLE = re.compile(
    rf"^第 ?([0-9一二三四五六七八九十百]+) ?条((?: ?の ?[0-9一二三四五六七八九十]+)*)"
    rf"(?:{SP}*[（(]([^）)]{{1,40}})[）)])?(?:{SP}+|$)(.*)$"
)
RE_CAPTION = re.compile(r"^[（(]([^）)]{1,40})[）)]$")
# 項：「2　…」のほか「2．…」「2. …」の書き方にも対応する
RE_PARAGRAPH = re.compile(rf"^([0-9]{{1,3}})(?:\.{SP}*|{SP}+)(.*)$")
# 号：「一　…」のほか「(1)　…」の書き方にも対応する（号の細分としての「(1)」と区別する）
RE_PAREN_ITEM = re.compile(rf"^[（(]([0-9]{{1,3}})[）)]{SP}*(.*)$")
RE_KANJI_OR_KANA_ITEM = re.compile(rf"^(?:[一二三四五六七八九十]+|[イロハニホヘトチリヌルヲワカヨタレソツネナラム]){SP}")
RE_ITEM = re.compile(rf"^([一二三四五六七八九十]+){SP}+(.*)$")
RE_SUBITEM = re.compile(rf"^(?:[イロハニホヘトチリヌルヲワカヨタレソツネナラム]|[（(][0-9]+[）)]){SP}*")
RE_VARIANT_NOTE = re.compile(r"^〔※.*〕$")
RE_VARIANT = re.compile(rf"^[（(]([アイウエオカキクケコ])[）)]{SP}*(.*)$")
RE_APPENDIX = re.compile(rf"^(附{SP}*則|別表)")
RE_PAGE_NO = re.compile(r"^[-－‐]?\s*[0-9]+\s*[-－‐]?$")
RE_DELETED = re.compile(rf"^[（(]削る[）)]$")


def normalize(s: str) -> str:
    """全角数字・全角英字を半角にし、前後の空白を取る（全角スペースは本文中に残す）。"""
    s = unicodedata.normalize("NFKC", s.replace("　", "￿")).replace("￿", "　")
    return s.strip(" \t\r\n　")


def kanji_to_int(s: str) -> int:
    """「十二」「百二十」などの漢数字を整数にする。算用数字はそのまま。"""
    if s.isdigit():
        return int(s)
    total, cur = 0, 0
    for ch in s:
        if ch == "百":
            total += (cur or 1) * 100
            cur = 0
        elif ch == "十":
            total += (cur or 1) * 10
            cur = 0
        else:
            cur = KANJI_NUM[ch]
    return total + cur


def article_number(main: str, branches: str) -> str:
    """「47」「の2」→「47の2」のように正規化した条番号を作る。"""
    num = str(kanji_to_int(main))
    for b in re.findall(r"の ?([0-9一二三四五六七八九十]+)", branches):
        num += f"の{kanji_to_int(b)}"
    return num


def drop_page_numbers(lines: list[str]) -> list[str]:
    """「- 22 -」のようなページ番号だけの行を取り除く。

    ヘッダー・フッターの除去はページ単位の情報が要るので、取り込み側（core/ingest.py）で行う。
    """
    return [line for line in lines if not RE_PAGE_NO.match(line)]


def split_kiyaku(raw_lines: list[str]) -> Kiyaku:
    lines = [normalize(x) for x in raw_lines]
    lines = drop_page_numbers([x for x in lines if x])

    kiyaku = Kiyaku()
    chapter = ""
    pending_caption = ""
    pending_note = ""
    variant: str | None = None
    variant_numbers: set[str] = set()  # （ア）の案に含まれる条番号
    in_second_variant = False
    in_appendix = False
    current: Article | None = None
    # 直前の要素（つなげ先）: ("para", Paragraph) / ("item", (Paragraph, idx)) / ("caption",) など
    last: tuple | None = None

    def append_to_last(text: str) -> None:
        nonlocal pending_caption
        if last is None:
            kiyaku.preamble.append(text)
        elif last[0] == "para":
            last[1].text += text
        elif last[0] == "item":
            para, idx = last[1]
            para.items[idx] += text
        elif last[0] == "preamble":
            kiyaku.preamble[-1] += text

    for line in lines:
        if in_appendix:
            kiyaku.appendix.append(line)
            continue
        if RE_APPENDIX.match(line):
            in_appendix = True
            kiyaku.appendix.append(line)
            continue
        if RE_CHAPTER.match(line):
            chapter = line
            variant, variant_numbers, in_second_variant = None, set(), False
            last = None
            continue
        if RE_SECTION.match(line):
            last = None
            continue
        if RE_VARIANT_NOTE.match(line):
            pending_note = line
            variant, variant_numbers, in_second_variant = None, set(), False
            last = None
            continue
        m = RE_VARIANT.match(line)
        if m and pending_note or (m and variant is not None):
            new_variant = m.group(1)
            if variant is not None and new_variant != variant:
                in_second_variant = True
            variant = new_variant
            last = None
            continue
        if RE_DELETED.match(line):
            continue
        m = RE_CAPTION.match(line)
        if m:
            pending_caption = m.group(1)
            last = None
            continue
        m = RE_ARTICLE.match(line)
        if m:
            number = article_number(m.group(1), m.group(2) or "")
            # 選択式の規定は、（ア）に含まれていた条番号の範囲で終わる
            if variant is not None:
                if in_second_variant and number not in variant_numbers:
                    variant, variant_numbers, in_second_variant = None, set(), False
                    pending_note = ""
                elif not in_second_variant:
                    variant_numbers.add(number)
            caption = m.group(3) or pending_caption
            current = Article(
                number=number,
                caption=caption,
                chapter=chapter,
                variant=variant,
                note=pending_note if variant is None or number in variant_numbers else "",
            )
            first = Paragraph(num=1, text=m.group(4))
            current.paragraphs.append(first)
            kiyaku.articles.append(current)
            pending_caption = ""
            if variant is None:
                pending_note = ""
            last = ("para", first)
            continue
        if current is None:
            kiyaku.preamble.append(line)
            last = ("preamble",)
            continue
        m = RE_PARAGRAPH.match(line)
        if m and int(m.group(1)) == len(current.paragraphs) + 1:
            para = Paragraph(num=int(m.group(1)), text=m.group(2))
            current.paragraphs.append(para)
            last = ("para", para)
            continue
        m = RE_ITEM.match(line)
        if m:
            para = current.paragraphs[-1]
            para.items.append(line)
            last = ("item", (para, len(para.items) - 1))
            continue
        m = RE_PAREN_ITEM.match(line)
        if m:
            # 直前が「一　」「イ　」の号なら、その細分。そうでなければ「(1)」形式の号
            if last and last[0] == "item":
                para, idx = last[1]
                if RE_KANJI_OR_KANA_ITEM.match(para.items[idx].split("\n")[-1]) or RE_KANJI_OR_KANA_ITEM.match(para.items[idx]):
                    para.items[idx] += "\n" + line
                    continue
            para = current.paragraphs[-1]
            para.items.append(line)
            last = ("item", (para, len(para.items) - 1))
            continue
        if RE_SUBITEM.match(line) and last and last[0] == "item":
            para, idx = last[1]
            para.items[idx] += "\n" + line
            continue
        append_to_last(line)

    return kiyaku
