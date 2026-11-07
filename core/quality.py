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


# 採点役のコメントに出てくる内部の言葉 → 使う人の言葉（長いものから置き換える）
GLOSSARY = [
    (r"/mnt/session/outputs/kaitei\.json", "改定案のファイル"),
    (r"kaitei\.json", "改定案"),
    (r"\{\s*\"?amendments\"?\s*:\s*\[(\d+)件\]\s*,\s*\"?notes\"?[^}]*\}", r"改定 \1件と申し送り"),
    (r"law_basis\s*と\s*standard_basis", "根拠（区分所有法と標準管理規約）"),
    (r"law_basis", "区分所有法の根拠"),
    (r"standard_basis", "標準管理規約の根拠"),
    (r"finding_refs", "対応する指摘の欄"),
    (r"check_draft", "改定案の自己点検"),
    (r"get_articles|get_rule_articles", "条文を取り寄せる機能"),
    (r"before_article", "改定前の条"),
    (r"\bnotes\b", "申し送り"),
    (r"\breason\b", "変える理由"),
    (r"\bdocument\b", "対象の文書"),
    (r"\bchoices\b", "選択肢の欄"),
    (r"\btext\b", "条文"),
    (r"ルーブリック", "確認項目"),
    (r"JSON", "決まった形"),
    (r"スキル", "手順書"),
    (r"\(met\)", "（満たす）"), (r"\(not met\)", "（満たさない）"), (r"\(partially met\)", "（一部満たす）"),
]
LIMIT = re.compile(r"[^。\n]*(?:できていません|できなかった|できません|使えない|使えません|手元にない|確認していません)[^。\n]*。?")


def plain(text: str) -> str:
    for pat, rep in GLOSSARY:
        text = re.sub(pat, rep, text)
    # 置き換えた言葉の前後に残る半角スペースを詰める（日本語の文字どうしの間だけ）
    text = re.sub(r"(?<=[^\x00-\x7F]) +(?=[^\x00-\x7F])", "", text)
    # 自己点検の実行記録は、アプリのプログラムによる確認で別に確かめているので、確認できなかった点からは外す
    text = re.sub(r"改定案の自己点検を実行した記録(?:と、)?", "", text)
    return text


def parse_explanation(text: str) -> dict:
    """採点役のコメントを、確認項目ごと（(1)〜(11)）の一行と、確認できなかった点に分ける。"""
    items: dict[int, str] = {}
    for m in re.finditer(r"^\s*\((\d{1,2})\)\s*(.+?)(?=^\s*\(\d{1,2}\)|\Z)", text, flags=re.MULTILINE | re.DOTALL):
        body = re.split(r"確認できなかった点|(?<=。)\s*(?:総じて|全体として|以上)", " ".join(m.group(2).split()))[0]  # 結びの文は外す
        items[int(m.group(1))] = plain(body.strip())
    limits = []
    for m in LIMIT.finditer(text):
        sentence = re.sub(r"^確認できなかった点[:：]\s*", "", plain(m.group(0).strip(" -・")))
        if sentence.rstrip("。").endswith(("確認できなかった点：", "確認できなかった点:")):
            continue
        if sentence and sentence not in limits:
            limits.append(sentence)
    return {"items": items, "limits": limits}


def _explanation_ja(text: str) -> str:
    """採点役のコメントの英語の部分を日本語にする（本文はもともと日本語）。"""
    text = re.sub(r"^An independent grader found all criteria met:?\s*", "確認役のまとめ：すべての項目を満たしています。\n", text)
    text = re.sub(r"^[A-Za-z][^\n]*:\s*\n", "", text)  # そのほかの英語の前置き
    return text.replace("(met)", "（満たす）").replace("(not met)", "（満たさない）").replace("(partially met)", "（一部満たす）")


def draft_quality(work: dict) -> dict:
    """改定案の確認結果（総合の判定・採点役の経過・プログラムの確認・件数・人が確認すること）。"""
    draft = work.get("draft") or {}
    amendments = draft.get("amendments", [])
    evals = work.get("draft_evaluations") or []
    rounds = [{"n": i + 1, "result": RESULT_JA.get(e.get("result"), e.get("result", "")),
               "ok": e.get("result") == "satisfied", "explanation": plain(_explanation_ja(e.get("explanation") or ""))}
              for i, e in enumerate(evals)]
    final = parse_explanation(evals[-1].get("explanation") or "") if evals else {"items": {}, "limits": []}
    ok_all = bool(evals) and evals[-1].get("result") == "satisfied"
    checklist = []
    for n, label in enumerate(RUBRIC_PLAIN, start=1):
        note = final["items"].get(n, "") if n != 1 else ""  # 1は形式の確認なので、説明は出さない
        bad = bool(re.search(r"満たさない|満たしていない|不足|誤り", note))
        checklist.append({"n": n, "label": label, "note": note, "ok": ok_all and not bad})
    last = evals[-1].get("result") if evals else ""
    if last == "satisfied":
        level = "ok"
        head = f"確認役（別の AI）の確認に合格しました（{len(evals)}回目で合格）"
        if len(evals) > 1:
            head += "。それまでの回で指摘された点は、AI が直しています"
    elif not evals:
        level = "warn"
        head = "確認役の確認が行われませんでした。新旧対照表を特に丁寧に確認してください"
    else:
        level = "warn"
        head = f"確認役の確認で、満たしていない項目が残った可能性があります（結果：{RESULT_JA.get(last, last)}）。下のコメントを読み、必要なら作り直してください"
    stop, plan = work.get("draft_stop", ""), work.get("draft_plan") or {}
    if stop == "timeout":  # 時間切れは、確認役の結果より先に知らせる（合否が出ないまま止まっている）
        level = "warn"
        head = (f"時間の上限（{plan.get('deadline_min', 30)}分）に達したため、途中で止まりました。"
                f"確認役の確認は{len(evals)}回目までで、直しきれていない点が残っている可能性があります。"
                "下のコメントを読み、作り直すか、採用する指摘を絞って作り直してください")
    elif stop and stop != "end_turn":
        level = "warn"
        head = f"AI の作業が途中で止まりました（費用の上限など。理由：{stop}）。新旧対照表を特に丁寧に確認し、必要なら作り直してください"
    by_doc: dict[str, int] = {}
    for a in amendments:
        by_doc[a.get("document") or "規約"] = by_doc.get(a.get("document") or "規約", 0) + 1
    choices = sum(1 for a in amendments if a.get("choices"))
    # 採用した指摘の対象ではない条の改定（参照の番号合わせなど）。採点役にも現行の文を渡していないので、人が確認する
    from core.sources import normalize_article_ref

    decisions = work.get("decisions", {})
    targets = {((f.get("document") or "規約"), normalize_article_ref(f["article"]))
               for i, f in enumerate(work.get("findings", []))
               if decisions.get(str(i), {}).get("decision") == "採用" and f.get("article") not in ("", "規定なし")}
    extra = [(f"{a.get('document')} " if (a.get("document") or "規約") != "規約" else "") + a.get("article", "")
             for a in amendments
             if a.get("kind") != "新設" and ((a.get("document") or "規約"), normalize_article_ref(a.get("article", ""))) not in targets]
    return {
        "level": level, "head": head, "rounds": rounds, "checklist": checklist, "limits": final["limits"],
        "checks_ok": not work.get("draft_errors"), "checks": CHECKS_PLAIN, "rubric": RUBRIC_PLAIN,
        "count": len(amendments), "by_doc": by_doc, "choices": choices, "extra": extra,
        "stopped": stop == "timeout" or bool(stop and stop != "end_turn"),
        "elapsed_min": round(work["draft_elapsed"] / 60, 1) if work.get("draft_elapsed") else None,
        "costs": cost_lines(work),
        "precedent": work.get("draft_precedent") or {},
    }


def _usd(cost) -> float | None:
    try:
        return int((cost or {}).get("amount")) / 100
    except (TypeError, ValueError):
        return None


def cost_lines(work: dict) -> dict:
    """これまでにかかった AI の費用（公開価格での概算）。作り直しても前の記録を残す。"""
    entries = list(work.get("costs") or [])
    if not entries:  # 記録を残す前の作業は、最後の値だけ
        entries = [{"step": s, "cost": work.get(k)} for s, k in (("点検", "review_cost"), ("改定案", "draft_cost")) if work.get(k)]
    lines = [{"step": e["step"], "usd": _usd(e.get("cost")), "at": e.get("at", "")} for e in entries]
    for b in work.get("notes") or []:  # 写真の書き込みの読み取り（写真ごとに記録している）
        if b.get("cost_usd"):
            lines.append({"step": f"書き込みの読み取り（写真{len(b.get('photos') or [])}枚）", "usd": round(b["cost_usd"], 2), "at": b.get("at", "")})
    lines = [x for x in lines if x["usd"] is not None]
    return {"lines": lines, "total": round(sum(x["usd"] for x in lines), 2)}


# 読み込んだ元のファイルの種類ごとの、「現行」欄の正確さと人が確認すること
SOURCE_NOTES = {
    "電子データ": "Word・テキストの電子データから読み込んだので、「現行」欄はほぼ正確です。ただし、その電子データが総会で改正した内容まで反映した最新版かは、改正履歴や原本で確かめてください。",
    "PDF": "PDF から読み込みました。改行やページ番号を取り除く処理で、文が崩れることがあります。特に数字（4分の3、1週間など）と条番号は、原本と照らし合わせてください。紙をスキャンして文字に起こした PDF の場合は、読み違いにも注意してください。",
    "サンプル": "サンプルのデータです。",
}


def source_kind(suffix: str, sample: bool = False) -> str:
    if sample:
        return "サンプル"
    return "PDF" if suffix.lower() == ".pdf" else "電子データ"

