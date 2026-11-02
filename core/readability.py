"""住民向け説明文の読みやすさの目安（自動計測）。

評価の本体は担当者による5段階評価（docs/SPEC.md）。ここで測るのは、その判断を助ける目安だけ。
  - 1文の長さ（平均・最大、60字を超える文の割合）
  - 言い換えや説明なしに使われている専門用語
"""

from __future__ import annotations

import re

# 住民向けの文章で、説明なしに使うと分かりにくい用語
JARGON = [
    "特別決議", "普通決議", "定足数", "議決権", "区分所有法", "区分所有者", "専有部分", "共用部分", "電磁的方法",
    "管理者", "代理行使", "不当利得", "所在等不明", "管理不全", "国内管理人", "枝番", "抵触", "敷地利用権",
    "保存行為", "別段の意思表示", "管理命令", "円滑化法",
]
LONG = 60


KANJI = re.compile(r"[\u4e00-\u9fff々]")


def _first_use(text: str, term: str) -> int:
    """用語が単独で使われた最初の位置。「防火管理者」の中の「管理者」のような、より長い語の一部は数えない。"""
    start = 0
    while (idx := text.find(term, start)) >= 0:
        if idx == 0 or not KANJI.match(text[idx - 1]):
            return idx
        start = idx + 1
    return -1


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[。！？])", text.replace("\n", "")) if s.strip()]


def measure(texts: list[str]) -> dict:
    sents = [s for t in texts for s in sentences(t)]
    lengths = [len(s) for s in sents]
    full = "".join(texts)
    unexplained = []
    for term in JARGON:
        idx = _first_use(full, term)
        if idx < 0:
            continue
        # 最初に出たところで説明があれば説明ありとみなす：
        #   直後に（説明）が続く、または「説明（用語）」のように用語自体が括弧に入っている
        after = full[idx + len(term): idx + len(term) + 1]
        before = full[idx - 1: idx] if idx > 0 else ""
        open_ = max(full.rfind("（", 0, idx), full.rfind("(", 0, idx))
        close_ = max(full.rfind("）", 0, idx), full.rfind(")", 0, idx))
        inside_parens = open_ > close_  # 「理事長（法律上の管理者＝…）」のように括弧の中の説明で使っている
        if after in ("（", "(") or (before in ("（", "(") and after in ("）", ")")) or inside_parens:
            continue
        unexplained.append(term)
    return {
        "文の数": len(sents),
        "1文の平均の長さ": round(sum(lengths) / len(lengths), 1) if lengths else 0,
        "最も長い文": max(lengths) if lengths else 0,
        f"{LONG}字を超える文の割合(%)": round(100 * sum(1 for x in lengths if x > LONG) / len(lengths), 1) if lengths else 0,
        "説明なしの専門用語": unexplained,
    }


def measure_explanation(ex) -> dict:
    # 資料に載る順（冒頭 → 各項目 → ご意見を伺いたい点 → 決め方 → 結び）
    texts = [ex.intro]
    for it in ex.items:
        texts += [it.what, it.why, it.impact]
    texts += [*ex.choices, ex.resolution, ex.closing]
    return measure(texts)
