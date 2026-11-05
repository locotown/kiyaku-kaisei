"""処理中の進み具合を、使う人に分かる言葉で示す。

AI が呼んだツールを日本語の作業内容に言い換え、作業の記録から「いまどの段階か」と件数をまとめる。
"""

from __future__ import annotations

import re

# 処理ごとの段階と、かかる時間の目安（evals/results の実測：点検 約3〜4分、改定案 約10〜12分、資料・説明 約1.5分）
STAGES = {
    "点検中": {"steps": ["手順を確認", "規約を読む", "標準管理規約・法律と照らし合わせ", "指摘を記録"], "estimate": "3〜5分"},
    "改定案作成中": {"steps": ["手順を確認", "条文を読む", "改定案を書く", "改定案を自分で点検", "採点役が確認"],
                  "estimate": "10〜15分"},
    "検討資料作成中": {"steps": ["改定案を読む", "検討資料を書く"], "estimate": "1〜2分"},
    "説明文作成中": {"steps": ["改定案を読む", "説明文を書く"], "estimate": "1〜2分"},
}

# 改定案の時間・費用は、採用した指摘の件数で大きく変わる（11/3 の通しテストの実測：
# 7件 約5分・$1.3、12〜13件 8〜12分・$2.5〜3.4、21件 30分で打ち切り・$5.4）。
# 件数ごとに目安を示し、時間と費用の上限も件数に合わせて広げる。
DRAFT_PLANS = [
    (8, {"estimate": "5〜10分", "cost": "$1〜2", "deadline_min": 30, "budget_usd": 5}),
    (15, {"estimate": "10〜20分", "cost": "$2〜4", "deadline_min": 30, "budget_usd": 5}),
    (10**6, {"estimate": "20〜45分", "cost": "$4〜8", "deadline_min": 50, "budget_usd": 9}),
]


def draft_plan(adopted: int) -> dict:
    """採用した指摘の件数から、改定案の時間・費用の目安と、打ち切る上限を返す。"""
    for limit, plan in DRAFT_PLANS:
        if adopted <= limit:
            return {"adopted": adopted, **plan, "large": limit > 15}
    raise AssertionError


# ツール名 → （段階の番号、言い換え）
TOOLS = {
    "list_articles": (1, "規約の条の一覧を確認"),
    "get_articles": (1, "規約の条文を確認"),
    "list_rules": (1, "細則の一覧を確認"),
    "get_rule_articles": (1, "細則の条文を確認"),
    "get_standard_articles": (2, "標準管理規約と照らし合わせ"),
    "get_law_articles": (2, "区分所有法と照らし合わせ"),
    "record_findings": (3, "指摘を記録"),
    "check_draft": (3, "改定案を自分で点検"),
    "share_references": (3, "参照先の条の現行の文を採点役に渡す"),
}
BUILTIN = {"read": "手順書を読む", "glob": "手順書を探す", "grep": "手順書を検索", "write": "改定案を書く", "edit": "改定案を直す"}


def _refs(items: list, limit: int = 4) -> str:
    items = [str(x) for x in items]
    s = "・".join(items[:limit])
    return s + (f" ほか{len(items) - limit}件" if len(items) > limit else "")


def describe_tool(name: str, args: dict | None = None) -> str:
    """ツールの呼び出しを「get_articles：規約の条文を確認：第45条・第47条」のような1行にする（先頭はツール名）。"""
    args = args or {}
    label = TOOLS.get(name, (0, name))[1]
    detail = ""
    if args.get("articles"):
        detail = _refs(args["articles"])
        if name == "get_rule_articles" and args.get("rule"):
            detail = f"{args['rule']} {detail}"
    elif name == "record_findings":
        detail = f"{len(args.get('findings', []))}件"
    return f"{name}：{label}" + (f"：{detail}" if detail else "")


def describe_builtin(name: str) -> str:
    return f"{name}：{BUILTIN.get(name, '資料を読む')}"


def _tool_name(entry: dict) -> str:
    return str(entry.get("text", "")).split("：", 1)[0]


PARTIAL = {"steps": ["対象の条を読む", "対象の条を書き直す", "直した条を確かめる"], "estimate": "2〜5分"}


def summarize(status: str, log: list[dict], adopted: int | None = None, partial: bool = False) -> dict:
    """この処理の作業の記録（log）から、段階と件数をまとめる。adopted は改定案に入れる指摘の件数（目安に使う）。

    partial は、理事会の判断を対象の条だけに反映する作り直し（段階が少なく、数分で終わる）。
    """
    if status == "改定案作成中" and partial:
        kinds = {e.get("kind") for e in log}
        stage = 2 if kinds & {"grading", "graded"} else 1 if "builtin" in kinds else 0
        return {**PARTIAL, "stage": stage, "counts": {"規約の条": 0, "標準管理規約": 0, "区分所有法": 0, "指摘": 0}}
    spec = dict(STAGES.get(status, {"steps": [], "estimate": ""}))
    if status == "改定案作成中" and adopted is not None:
        spec["estimate"] = draft_plan(adopted)["estimate"]
    stage, counts = 0, {"規約の条": 0, "標準管理規約": 0, "区分所有法": 0, "指摘": 0}
    for e in log:
        kind, name = e.get("kind"), _tool_name(e)
        if kind == "tool":
            stage = max(stage, TOOLS.get(name, (0, ""))[0])
            if name in ("get_articles", "get_rule_articles"):
                counts["規約の条"] += 1
            elif name == "get_standard_articles":
                counts["標準管理規約"] += 1
            elif name == "get_law_articles":
                counts["区分所有法"] += 1
        elif kind == "found":
            m = re.search(r"合計(\d+)件", str(e.get("text", "")))
            if m:
                counts["指摘"] = int(m.group(1))
        elif kind == "builtin" and name in ("write", "edit"):
            stage = max(stage, 2)
        elif kind in ("grading", "graded"):
            stage = max(stage, 4)
        elif kind == "writing":
            stage = max(stage, 1)
    if status in ("検討資料作成中", "説明文作成中"):
        stage = 1 if log else 0
    stage = min(stage, max(len(spec["steps"]) - 1, 0))
    return {"steps": spec["steps"], "stage": stage, "estimate": spec["estimate"], "counts": counts}
