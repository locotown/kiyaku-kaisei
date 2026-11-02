"""試験用の「長く改正していない規約」（架空、evals/data/old_style_kiyaku.txt）で点検を評価する。

標準管理規約と条番号・構成が違う規約でも、必須の論点を見つけ、正しい条を指せるかを測る。

指標:
  - 必須の検出率      … 必須の論点のうち、指摘できた割合
  - 必須の条の特定    … 必須の論点の指摘が、正解の条（条番号がずれた後の番号）を指している割合
  - 受け付けなかった指摘、指摘の件数と内訳、費用

使い方:  uv run python -m evals.run_eval_old
結果は evals/results/old_style/<日時>.json と .md。続けて改定案を作るには
  uv run python -m evals.run_draft evals/results/old_style/<日時>.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime

from core.config import ROOT
from core.ingest import load_kiyaku
from core.review import JST, run_review
from core.sources import normalize_article_ref
from core.topics import REQUIRED_TOPIC_IDS

DATA = ROOT / "evals/data"
OUT = ROOT / "evals/results/old_style"
INPUT = DATA / "old_style_kiyaku.txt"

BASIC_INFO = {
    "型": "単棟型",
    "電磁的方法の利用": "未定",
    "備考": "長く規約を改正していない（評価用の架空の規約）",
}


def score(findings: list[dict], gold: dict) -> dict:
    hit, located = [], []
    for t in REQUIRED_TOPIC_IDS:
        mine = [f for f in findings if f["topic_id"] == t]
        if mine:
            hit.append(t)
            expected = {normalize_article_ref(x) for x in gold["required"][t]["articles"]}
            if any(normalize_article_ref(f["article"]) in expected for f in mine if f["article"] != "規定なし"):
                located.append(t)
    n = len(REQUIRED_TOPIC_IDS)
    return {
        "指摘の件数": len(findings),
        "区分の内訳": {c: sum(1 for f in findings if f["category"] == c) for c in ("必須", "推奨", "参考")},
        "必須の検出率": f"{len(hit)}/{n}",
        "必須の条の特定": f"{len(located)}/{n}",
        "検出できなかった必須の論点": [t for t in REQUIRED_TOPIC_IDS if t not in hit],
        "条を取り違えた必須の論点": [t for t in hit if t not in located],
        "検出した論点": sorted({f["topic_id"] for f in findings}),
    }


def main() -> None:
    gold = json.loads((DATA / "old_style_gold.json").read_text(encoding="utf-8"))
    kiyaku = load_kiyaku(INPUT)

    def progress(kind: str, text: str) -> None:
        if kind == "session":
            print(f"セッション開始: {text}", flush=True)
        elif kind == "tool" and text == "record_findings":
            print("  [ツール] record_findings", flush=True)
        elif kind == "error":
            print(f"  [エラー] {text}", file=sys.stderr, flush=True)

    result = run_review(kiyaku, BASIC_INFO, on_event=progress, title="評価：古い規約（架空）").to_dict()
    result["input"] = str(INPUT.relative_to(ROOT))
    result["basic_info"] = BASIC_INFO
    metrics = score(result["findings"], gold)
    metrics.update({"受け付けなかった指摘": len(result["rejected"]), "費用": result["usage"].get("list_cost"),
                    "所要時間(秒)": result["elapsed_sec"]})

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(JST).strftime("%Y%m%d-%H%M")
    (OUT / f"{stamp}.json").write_text(json.dumps({"metrics": metrics, "result": result}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [f"# 評価結果（古い規約・架空） {stamp}", "", "| 指標 | 値 |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k, v in metrics.items()]
    lines += ["", "## 指摘", "", "| 区分 | 条 | 論点 | 根拠（法） | 根拠（標準） |", "| --- | --- | --- | --- | --- |"]
    lines += [f"| {f['category']} | {f['article']} | {f['topic_id']} | {'、'.join(f['law_basis'])} | {'、'.join(f['standard_basis'])} |"
              for f in result["findings"]]
    (OUT / f"{stamp}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"保存: evals/results/old_style/{stamp}.json")


if __name__ == "__main__":
    main()
