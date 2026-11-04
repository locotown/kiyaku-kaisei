"""規約本体と細則をまとめて扱う。

文書の名前は、規約本体が「規約」、細則はその題名（例：「○○マンション駐車場使用細則」）。
指摘や改定案の document 欄にこの名前を入れる。題名の一部（「駐車場使用細則」）でも引けるようにする。
"""

from __future__ import annotations

from core.model import Article, Kiyaku

MAIN = "規約"


class Corpus:
    def __init__(self, main: Kiyaku, rules: dict[str, Kiyaku] | None = None):
        self.main = main
        self.rules = rules or {}

    @classmethod
    def of(cls, x) -> "Corpus":
        return x if isinstance(x, Corpus) else cls(x)

    @classmethod
    def from_collection(cls, collection) -> "Corpus":
        main = collection.main.kiyaku if collection.main and collection.main.kiyaku else Kiyaku()
        rules = {d.title: d.kiyaku for d in collection.rules if d.kiyaku and d.kiyaku.articles}
        return cls(main, rules)

    def names(self) -> list[str]:
        return [MAIN, *self.rules]

    def resolve(self, document: str | None) -> str | None:
        """文書の名前を正式な名前にする。見つからなければ None。"""
        doc = (document or MAIN).strip()
        if doc in (MAIN, "管理規約", "規約本体"):
            return MAIN
        if doc in self.rules:
            return doc
        matches = [name for name in self.rules if doc in name or name in doc]
        return matches[0] if len(matches) == 1 else None

    def get(self, document: str | None) -> Kiyaku | None:
        name = self.resolve(document)
        if name is None:
            return None
        return self.main if name == MAIN else self.rules[name]

    def find(self, document: str | None, number: str) -> list[Article]:
        k = self.get(document)
        return [a for a in k.articles if a.number == number] if k else []

    @staticmethod
    def resolution(document: str | None) -> str:
        """その文書を変えるのに必要な総会の決議。"""
        return "特別決議" if (document or MAIN) == MAIN else "普通決議"
