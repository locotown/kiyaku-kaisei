"""正解データ（evals/data/r7_tantou_gold.json）で、点検の精度を測る。

入力：改正前（令和6年版相当）の標準管理規約（単棟型）の本文
正解：令和7年改正で変わった条と、docs/DOMAIN.md の論点・区分

指標（docs/SPEC.md「7. 評価方法」）:
  - 必須の検出率（再現率）  … 必須の論点のうち、指摘できた割合（目標 100%）
  - 指摘の正確さ（適合率）  … 指摘のうち、正解の変更（改正で変わった条・論点）に当たる割合（目標 80%以上）
  - 根拠の正しさ            … 既知の論点の指摘で、根拠の条文が論点表の条文と合っている割合（目標 95%以上）
  - 区分の一致              … 既知の論点の指摘で、区分が論点表と一致する割合（記録のみ）
住民向け説明の読みやすさは、担当者が5段階で評価する（このスクリプトの対象外）。

使い方:  uv run python -m evals.run_eval
結果は evals/results/ に JSON と Markdown で保存する。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from core.config import ROOT
from core.ingest import load_kiyaku
from core.review import run_review
from core.sources import normalize_article_ref
from core.topics import REQUIRED_TOPIC_IDS, TOPIC_BY_ID

DATA = ROOT / "evals/data"
RESULTS = ROOT / "evals/results"
JST = timezone(timedelta(hours=9))

BASIC_INFO = {
    "型": "単棟型",
    "電磁的方法の利用": "未定（選択式の規定は担当者が選ぶ）",
    "備考": "評価用。国交省の標準管理規約（令和7年改正前の版）をそのまま使っている",
}


def score(findings: list[dict], gold: dict) -> dict:
    changed_before = {c["before_key"].split("(")[0] for c in gold["changes"] if c["before_key"]}
    new_articles = {c["key"].split("(")[0] for c in gold["changes"] if c["change"] == "新設"}

    found_topics = {f["topic_id"] for f in findings}
    required_hit = [t for t in REQUIRED_TOPIC_IDS if t in found_topics]

    correct = 0
    basis_ok = basis_total = 0
    for f in findings:
        number = normalize_article_ref(f["article"]) if f["article"] != "規定なし" else None
        std_numbers = {normalize_article_ref(x) for x in f["standard_basis"]}
        is_correct = (f["topic_id"] in TOPIC_BY_ID) or (number in changed_before) or bool(std_numbers & new_articles)
        correct += is_correct
        if f["topic_id"] in TOPIC_BY_ID:
            t = TOPIC_BY_ID[f["topic_id"]]
            basis_total += 1
            law_numbers = {normalize_article_ref(x) for x in f["law_basis"]}
            ok_std = bool(std_numbers & set(t["standard"])) or not std_numbers
            ok_law = (not t["law"] and not law_numbers) or bool(law_numbers & set(t["law"])) or (not law_numbers and std_numbers)
            basis_ok += bool(ok_std and ok_law)

    n = len(findings)
    return {
        "指摘の件数": n,
        "必須の検出率": f"{len(required_hit)}/{len(REQUIRED_TOPIC_IDS)}",
        "必須の検出率(%)": round(100 * len(required_hit) / len(REQUIRED_TOPIC_IDS), 1),
        "検出できなかった必須の論点": [t for t in REQUIRED_TOPIC_IDS if t not in found_topics],
        "指摘の正確さ(%)": round(100 * correct / n, 1) if n else None,
        "根拠の正しさ(%)": round(100 * basis_ok / basis_total, 1) if basis_total else None,
        "検出した論点": sorted(found_topics),
        "区分の内訳": {c: sum(1 for f in findings if f["category"] == c) for c in ("必須", "推奨", "参考")},
    }


def to_markdown(result: dict, metrics: dict, stamp: str) -> str:
    lines = [f"# 評価結果 {stamp}", "", "入力：改正前の標準管理規約（単棟型）／正解：国交省の見え消し", ""]
    lines += ["| 指標 | 値 | 目標 |", "| --- | --- | --- |"]
    lines.append(f"| 必須の検出率 | {metrics['必須の検出率']}（{metrics['必須の検出率(%)']}%） | 100% |")
    lines.append(f"| 指摘の正確さ | {metrics['指摘の正確さ(%)']}% | 80%以上 |")
    lines.append(f"| 根拠の正しさ | {metrics['根拠の正しさ(%)']}% | 95%以上 |")
    lines.append(f"| 指摘の件数 | {metrics['指摘の件数']}（{metrics['区分の内訳']}） | — |")
    lines += ["", f"- 検出できなかった必須の論点：{metrics['検出できなかった必須の論点'] or 'なし'}",
              f"- 受け付けなかった指摘：{len(result['rejected'])}件",
              f"- 所要時間：{result['elapsed_sec']}秒／終了理由：{result['stop']}",
              f"- セッション：{result['session_id']}", ""]
    lines += ["## 指摘の一覧", "", "| 区分 | 条 | 論点 | 根拠（法） | 根拠（標準） | 規約/細則 |", "| --- | --- | --- | --- | --- | --- |"]
    for f in result["findings"]:
        lines.append(f"| {f['category']} | {f['article']} | {f['topic_id']} | {'、'.join(f['law_basis'])} | {'、'.join(f['standard_basis'])} | {f['where']} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    gold = json.loads((DATA / "r7_tantou_gold.json").read_text(encoding="utf-8"))
    kiyaku = load_kiyaku(DATA / "r7_tantou_before.txt")

    def progress(kind: str, text: str) -> None:
        if kind == "tool":
            print(f"  [ツール] {text}", flush=True)
        elif kind == "session":
            print(f"セッション開始: {text}", flush=True)
        elif kind == "error":
            print(f"  [エラー] {text}", file=sys.stderr, flush=True)

    result = run_review(kiyaku, BASIC_INFO, on_event=progress, title="評価：改正前の標準管理規約").to_dict()
    metrics = score(result["findings"], gold)

    RESULTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(JST).strftime("%Y%m%d-%H%M")
    (RESULTS / f"{stamp}.json").write_text(
        json.dumps({"metrics": metrics, "result": result}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RESULTS / f"{stamp}.md").write_text(to_markdown(result, metrics, stamp), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"保存: evals/results/{stamp}.md")


if __name__ == "__main__":
    main()
