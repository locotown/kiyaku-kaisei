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


def summarize(status: str, log: list[dict]) -> dict:
    """この処理の作業の記録（log）から、段階と件数をまとめる。"""
    spec = STAGES.get(status, {"steps": [], "estimate": ""})
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
