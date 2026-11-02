"""判断の履歴（指摘の判断・理事会の判断で共通）。

判断を変えるたびに「日時・前の判断 → 新しい判断・理由」を1件追加する。
判断を変えずに理由だけ直した場合は、最新の1件の理由を書き直す（入力のたびに履歴が増えないように）。
"""

from __future__ import annotations


def record(old: dict | None, decision: str, reason: str, at: str, reason_key: str = "reason",
           extra: dict | None = None) -> list[dict]:
    """新しい判断を反映した履歴を返す（old は保存済みの判断。history を含む）。"""
    old = old or {}
    hist = [dict(e) for e in old.get("history", [])]
    before = old.get("decision", "")
    extra = {k: v for k, v in (extra or {}).items() if v}
    if decision != before:
        if decision:
            hist.append({"at": at, "from": before, "to": decision, "reason": reason, **extra})
    elif reason != old.get(reason_key, "") or any(old.get(k, "") != v for k, v in extra.items()):
        if hist and hist[-1].get("to") == decision:
            hist[-1].update({"reason": reason, "edited_at": at, **extra})
        elif decision:
            hist.append({"at": at, "from": decision, "to": decision, "reason": reason, **extra})
    return hist


def line(e: dict) -> str:
    """履歴1件を1行の文にする（画面と印刷用で共通）。"""
    head = f"{e['to']}（理由を記入）" if e.get("from") == e["to"] else f"{e.get('from') or '（初期）'} → {e['to']}"
    s = f"{e['at']}　{head}"
    if e.get("choice"):
        s += f"　選んだ案：{e['choice']}"
    if e.get("reason"):
        s += f"　「{e['reason']}」"
    if e.get("edited_at"):
        s += f"（{e['edited_at']} に理由を修正）"
    return s
