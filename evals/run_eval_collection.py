"""試験用の規約集（架空：古い規約＋細則3種、evals/data/old_collection.txt）で点検を評価する。

指標:
  - 規約本体の必須の検出率・条の特定（evals/run_eval_old.py と同じ）
  - 細則に仕込んだ問題の検出（文書と条が一致する指摘があるか）
  - 問題のない細則への指摘（誤り）の件数

使い方:  uv run python -m evals.run_eval_collection
続けて改定案：  uv run python -m evals.run_draft evals/results/collection/<日時>.json
"""

from __future__ import annotations

import json
import sys
from datetime import datetime

from core.config import ROOT
from core.corpus import Corpus
from core.ingest import load_collection
from core.review import JST, run_review
from core.sources import normalize_article_ref
from evals.run_eval_old import score as score_main

DATA = ROOT / "evals/data"
OUT = ROOT / "evals/results/collection"
INPUT = DATA / "old_collection.txt"

BASIC_INFO = {
    "型": "単棟型",
    "電磁的方法の利用": "未定",
    "備考": "長く規約を改正していない。規約集に細則がある（評価用の架空の規約集）",
}


def score(findings: list[dict], gold: dict, corpus: Corpus) -> dict:
    main_findings = [f for f in findings if f.get("document", "規約") == "規約"]
    metrics = score_main(main_findings, gold)
    hits, missed = [], []
    for p in gold["planted"]:
        doc = corpus.resolve(p["document"])
        found = [f for f in findings if f.get("document") == doc and f["article"] != "規定なし"
                 and normalize_article_ref(f["article"]) == p["article"]]
        (hits if found else missed).append(f"{p['document']} 第{p['article']}条：{p['kind']}")
    clean = [corpus.resolve(x) for x in gold["clean_rules"]]
    false_pos = [f"{f['document']} {f['article']}：{f['issue'][:40]}" for f in findings if f.get("document") in clean]
    metrics.update({
        "細則に仕込んだ問題の検出": f"{len(hits)}/{len(gold['planted'])}",
        "見つけられなかった問題": missed,
        "問題のない細則への指摘（誤り）": false_pos,
        "細則への指摘の件数": sum(1 for f in findings if f.get("document", "規約") != "規約"),
    })
    return metrics


def main() -> None:
    gold = json.loads((DATA / "old_collection_gold.json").read_text(encoding="utf-8"))
    corpus = Corpus.from_collection(load_collection(INPUT))

    def progress(kind: str, text: str) -> None:
        if kind == "session":
            print(f"セッション開始: {text}", flush=True)
        elif kind == "tool" and text in ("record_findings", "list_rules", "get_rule_articles"):
            print(f"  [ツール] {text}", flush=True)
        elif kind == "error":
            print(f"  [エラー] {text}", file=sys.stderr, flush=True)

    result = run_review(corpus.main, BASIC_INFO, rules=corpus.rules, on_event=progress,
                        title="評価：規約集（古い規約＋細則、架空）").to_dict()
    result.update({"input": str(INPUT.relative_to(ROOT)), "basic_info": BASIC_INFO, "collection": True})
    metrics = score(result["findings"], gold, corpus)
    metrics.update({"受け付けなかった指摘": len(result["rejected"]), "費用": result["usage"].get("list_cost"),
                    "所要時間(秒)": result["elapsed_sec"]})

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(JST).strftime("%Y%m%d-%H%M")
    (OUT / f"{stamp}.json").write_text(json.dumps({"metrics": metrics, "result": result}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [f"# 評価結果（規約集・架空） {stamp}", "", "| 指標 | 値 |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k, v in metrics.items()]
    lines += ["", "## 指摘", "", "| 区分 | 文書 | 条 | 論点 | 内容 |", "| --- | --- | --- | --- | --- |"]
    lines += [f"| {f['category']} | {f.get('document', '規約')} | {f['article']} | {f['topic_id']} | {f['issue'][:60]} |"
              for f in result["findings"]]
    (OUT / f"{stamp}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"保存: evals/results/collection/{stamp}.json")


if __name__ == "__main__":
    main()
