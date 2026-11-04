"""規約を条・項・号の単位で表すデータ構造。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Paragraph:
    """項。num は項番号（第1項は 1）。items は号（一、二…）の本文。"""

    num: int
    text: str
    items: list[str] = field(default_factory=list)


@dataclass
class Article:
    """条。

    number は正規化した条番号（例："47", "24の2"）。
    variant は選択式の規定の案（例："ア"）。選択式でなければ None。
    note は直前に置かれた「〔※…〕」の注記。
    """

    number: str
    caption: str = ""
    paragraphs: list[Paragraph] = field(default_factory=list)
    chapter: str = ""
    variant: str | None = None
    note: str = ""
    style: str = "条"  # 「条」（第1条…）または「項目」（1. 管理員 … のような細則の書き方）

    @property
    def key(self) -> str:
        """同じ条番号の選択肢を区別するキー（例："17", "17(ア)"）。"""
        return f"{self.number}({self.variant})" if self.variant else self.number

    @property
    def label(self) -> str:
        """表示用の条番号（例："第47条", "第24条の2"）。"""
        if self.style == "項目":
            return f"{self.number}."
        head, *rest = self.number.split("の")
        return f"第{head}条" + "".join(f"の{r}" for r in rest)

    def text(self) -> str:
        """条の本文をひとつの文字列にする（見出しを含む）。"""
        lines = [f"（{self.caption}）"] if self.caption else []
        for p in self.paragraphs:
            prefix = f"{self.label}　" if p.num == 1 else f"{p.num}　"
            lines.append(prefix + p.text)
            lines.extend(p.items)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return asdict(self) | {"key": self.key, "label": self.label}


@dataclass
class Kiyaku:
    """規約全体。articles は本文の条。appendix は附則・別表など、条以外の部分。"""

    articles: list[Article] = field(default_factory=list)
    preamble: list[str] = field(default_factory=list)
    appendix: list[str] = field(default_factory=list)

    def find(self, number: str, variant: str | None = None) -> Article | None:
        for a in self.articles:
            if a.number == number and (variant is None or a.variant == variant):
                return a
        return None

    def keys(self) -> list[str]:
        return [a.key for a in self.articles]

    def to_dict(self) -> dict:
        return {
            "articles": [a.to_dict() for a in self.articles],
            "preamble": self.preamble,
            "appendix": self.appendix,
        }
