"""改定案の確認結果を、使う人に分かる言葉で示す。

改定案は2段階で確認している。
  1. プログラムによる確認（core/draft.py の check）… 対象の条や根拠が実在するか、必須の指摘が入っているか など
  2. 採点役（別の AI）による確認（core/drafting.py の RUBRIC）… 11項目を独立に採点し、満たさなければ作り直させる
"""

from __future__ import annotations

import re

# 採点役の結果（Managed Agents の outcome の結果）→ 日本語
RESULT_JA = {
    "satisfied": "合格",
    "needs_revision": "直しが必要",
    "max_iterations_reached": "直す回数の上限に達した",
    "failed": "確認できなかった",
    "interrupted": "中断した",
}

# 採点役が確認する11項目（core/drafting.py の RUBRIC を、使う人向けの言葉にしたもの）
RUBRIC_PLAIN = [
    "改定案が決まった形で読み取れる",
    "必須の指摘がすべて改定案に入り、条文で解消されている",
    "改正区分所有法の数値（特別決議の出席と4分の3、招集通知の1週間、議案の要領）と合っている",
    "指摘と関係のない文言を変えていない（条番号を振り直していない）",
    "規約の書き方（条・項・号）と、今の規約の言い回しを引き継いでいる",
    "変える理由が、専門家でなくても分かる言葉で書かれている",
    "すべての改定に根拠（区分所有法・標準管理規約）がある",
    "組合が選ぶべき点（電磁的方法を使うかなど）を、勝手に決めていない",
    "条文中の「第○条」「前条」などの参照が、改定後の規約で正しい条を指している",
    "申し送り事項が見出しで整理され、「法的助言ではない」と書かれている",
    "規約と細則の振り分けが正しい",
]

# プログラムによる確認（core/draft.py の check）
CHECKS_PLAIN = [
    "改定する条が、今の規約・細則に実際にある",
    "新しく設ける条は枝番で、今ある条と重ならない",
    "すべての改定に、実在する根拠（区分所有法・標準管理規約の条）がある",
    "必須の指摘がすべて改定案に入っている",
    "同じ条の改定が重なっていない",
]


def _explanation_ja(text: str) -> str:
    """採点役のコメントの英語の部分を日本語にする（本文はもともと日本語）。"""
    text = re.sub(r"^An independent grader found all criteria met:?\s*", "採点役のまとめ：すべての項目を満たしています。\n", text)
    text = re.sub(r"^[A-Za-z][^\n]*:\s*\n", "", text)  # そのほかの英語の前置き
    return text.replace("(met)", "（満たす）").replace("(not met)", "（満たさない）").replace("(partially met)", "（一部満たす）")


def draft_quality(work: dict) -> dict:
    """改定案の確認結果（総合の判定・採点役の経過・プログラムの確認・件数・人が確認すること）。"""
    draft = work.get("draft") or {}
    amendments = draft.get("amendments", [])
    evals = work.get("draft_evaluations") or []
    rounds = [{"n": i + 1, "result": RESULT_JA.get(e.get("result"), e.get("result", "")),
               "ok": e.get("result") == "satisfied", "explanation": _explanation_ja(e.get("explanation") or "")}
              for i, e in enumerate(evals)]
    last = evals[-1].get("result") if evals else ""
    if last == "satisfied":
        level = "ok"
        head = f"採点役（別の AI）の確認に合格しました（{len(evals)}回目で合格）"
        if len(evals) > 1:
            head += "。それまでの回で指摘された点は、AI が直しています"
    elif not evals:
        level = "warn"
        head = "採点役の確認が行われませんでした。新旧対照表を特に丁寧に確認してください"
    else:
        level = "warn"
        head = f"採点役の確認で、満たしていない項目が残った可能性があります（結果：{RESULT_JA.get(last, last)}）。下のコメントを読み、必要なら作り直してください"
    by_doc: dict[str, int] = {}
    for a in amendments:
        by_doc[a.get("document") or "規約"] = by_doc.get(a.get("document") or "規約", 0) + 1
    choices = sum(1 for a in amendments if a.get("choices"))
    return {
        "level": level, "head": head, "rounds": rounds,
        "checks_ok": not work.get("draft_errors"), "checks": CHECKS_PLAIN, "rubric": RUBRIC_PLAIN,
        "count": len(amendments), "by_doc": by_doc, "choices": choices,
    }
