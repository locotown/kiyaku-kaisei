"""規約集（規約本体・細則・別表・改正履歴・作業メモが1つのファイルに入ったもの）を、文書ごとに分ける。

マンションによって規約集の作り方は違うため、ここでの判定は目安。画面で担当者が確認・修正できるようにする。

分け方:
  - 規約 … 「○○管理規約」のような題名の行から。附則・別表も規約の一部として持つ
  - 細則 … 「○○使用細則」「○○細則」「○○規程」の題名の行から。条形式（第1条…）と項目形式（1. 管理員…）がある
  - 改正履歴 … 「改正履歴」「改訂履歴」を含む見出しから
  - メモ … 最初の題名より前の部分（表紙、反映範囲の説明など）
本文から外すもの（各文書の annotations に別に保持する）:
  - ページ参照：「（規約集 p11）」「(p05-p06)」など
  - 注記：◆ ★ ※ で始まる行、「- 」で始まる箇条書きの行、「出典 = …」「旧条文 = …」のような作業の記録
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.model import Kiyaku
from core.split import normalize, split_kiyaku

PAGE_REF = re.compile(r"[\s　]*[（(]\s*(?:規約集\s*)?p\.?\s*\d+(?:\s*[-–~〜]\s*p?\.?\s*\d+)?\s*[）)]")
MARKER_TAIL = re.compile(r"[\s　]*[◆★]+$")
# 注記：◆★※で始まる行、「- 」の箇条書き、「出典 = …」「旧条文 = …」のような記録の行。
# 標準管理規約の選択式の注記「〔※…〕」は条文の一部なので含めない
ANNOTATION = re.compile(
    r"^(?:[◆★※]|-\s|[（(]旧\s*[=＝]|・?[^\s=＝。、]{1,10}\s*[=＝]|・?(?:出典|原本|決議|旧条文|改正前|改正後)\s*[:：])"
)
# 題名の後ろに続けてよいのは「（2026-11-01 追加）」のような括弧書きだけ（表の行などを題名と誤らないため）
TITLE = re.compile(r"^(?P<title>[^第\d（(※\-].{0,40}?(?:管理規約|規約|細則|規程|協定))(?:[\s　]*[（(][^）)]{0,30}[）)])?$")
HISTORY = re.compile(r"(改正|改訂)(履歴|の記録)")
ITEM_HEADING = re.compile(r"^(\d{1,2})\.\s*(\S.{0,20})$")
APPENDIX_HEAD = re.compile(r"^(附[\s　]*則|別表)")

KINDS = ("規約", "細則", "改正履歴", "メモ")


@dataclass
class Document:
    kind: str
    title: str
    lines: list[str] = field(default_factory=list)
    annotations: list[str] = field(default_factory=list)
    kiyaku: Kiyaku | None = None

    @property
    def style(self) -> str:
        if not self.kiyaku or not self.kiyaku.articles:
            return ""
        return self.kiyaku.articles[0].style

    def summary(self) -> dict:
        return {
            "kind": self.kind,
            "title": self.title,
            "lines": len(self.lines),
            "articles": len(self.kiyaku.articles) if self.kiyaku else 0,
            "style": self.style,
            "annotations": len(self.annotations),
            "appendix_lines": len(self.kiyaku.appendix) if self.kiyaku else 0,
        }


@dataclass
class Collection:
    documents: list[Document]

    @property
    def main(self) -> Document | None:
        """規約本体（最初の「規約」）。"""
        return next((d for d in self.documents if d.kind == "規約"), None)

    @property
    def rules(self) -> list[Document]:
        """細則の一覧。"""
        return [d for d in self.documents if d.kind == "細則"]

    def summary(self) -> list[dict]:
        return [d.summary() for d in self.documents]


def clean_line(line: str) -> str:
    """ページ参照と行末の◆★を取り除く。"""
    line = PAGE_REF.sub("", line)
    return MARKER_TAIL.sub("", line).rstrip()


COVER = re.compile(r"規約[・及び、]+細則")


def classify_title(line: str) -> str | None:
    """題名の行なら文書の種類を返す。"""
    if ANNOTATION.match(line):
        return None
    if COVER.search(line) and not HISTORY.search(line):
        return "メモ"  # 「○○管理規約・細則」のような規約集全体の表紙
    if HISTORY.search(line) and len(line) <= 40:
        return "改正履歴"
    m = TITLE.match(line)
    if not m:
        return None
    title = m.group("title")
    if re.search(r"(細則|規程)$", title):
        return "細則"
    if title.endswith("規約") or title.endswith("管理規約") or title.endswith("協定"):
        return "規約"
    return None


def _is_body_sentence(line: str) -> bool:
    # 「この規約は、…」「…規約を遵守しなければならない。」のような本文の文は題名ではない
    return "。" in line or "、" in line[:15]


def segment(raw_lines: list[str]) -> Collection:
    docs: list[Document] = [Document(kind="メモ", title="（表紙・作業メモ）")]
    for raw in raw_lines:
        line = normalize(raw)
        if not line:
            continue
        stripped = clean_line(line)
        if ANNOTATION.match(stripped):
            docs[-1].annotations.append(stripped)
            continue
        kind = classify_title(stripped) if not _is_body_sentence(stripped) else None
        if kind == "メモ":
            if docs[-1].kind == "メモ":
                docs[-1].title = stripped
            else:
                docs.append(Document(kind="メモ", title=stripped))
            continue
        if kind and not (kind == "規約" and docs[-1].kind == "規約" and not docs[-1].lines):
            docs.append(Document(kind=kind, title=stripped))
            continue
        if stripped:
            docs[-1].lines.append(stripped)
    docs = [d for d in docs if d.lines or d.annotations or d.kind != "メモ"]
    for d in docs:
        if d.kind in ("規約", "細則"):
            d.kiyaku = _parse(d.lines)
    return Collection(documents=docs)


def _parse(lines: list[str]) -> Kiyaku:
    """条形式はそのまま分割する。条がなく「1. 見出し」の項目形式なら、項目を条として扱う。"""
    if any(re.match(r"^第\s?[0-9一二三四五六七八九十百]+\s?条", x) for x in lines):
        return split_kiyaku(lines)
    converted = []
    for x in lines:
        m = ITEM_HEADING.match(x)
        if m and not x.endswith("。"):
            converted += [f"（{m.group(2)}）", f"第{m.group(1)}条"]
        else:
            converted.append(x)
    k = split_kiyaku(converted)
    for a in k.articles:
        a.style = "項目"
    return k
