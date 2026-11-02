"""改定案と新旧対照表を作り、評価する。

入力：改正前の標準管理規約（単棟型）と、点検の評価結果（evals/results/*.json）の指摘
出力：evals/results/drafts/<日時>/ に kaitei.json、taisho.html、taisho.md、metrics.json

指標:
  - アプリ側の検査（core/draft.check）のエラー件数 … 0 が合格
  - 必須の指摘への対応 … 必須の論点が、いずれかの改定の finding_refs に入っているか
  - 採点役（Outcomes）の結果 … satisfied になったか、何回目で合格したか
  - （参考）国交省の改正後の条文との近さ … 改定した条ごとの文字列の一致度（0〜1）。
    一部改正なので完全一致はしないが、大きく外れていないかの目安にする

使い方:  uv run python -m evals.run_draft [点検結果のJSON]
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from difflib import SequenceMatcher

from core.config import ROOT
from core.drafting import run_draft
from core.findings import Finding
from core.ingest import load_kiyaku
from core.review import JST
from core.sources import normalize_article_ref
from core.split import split_kiyaku
from core.taisho import to_html, to_markdown
from evals.run_eval import BASIC_INFO

DATA = ROOT / "evals/data"
RESULTS = ROOT / "evals/results"


def latest_review() -> str:
    files = sorted(p for p in RESULTS.glob("*.json"))
    if not files:
        raise SystemExit("点検の評価結果がありません。先に uv run python -m evals.run_eval を実行してください。")
    return str(files[-1])


def _squash(s: str) -> str:
    return re.sub(r"[\s　（）()]", "", s)


def closeness(draft, after_text_path) -> dict:
    after = split_kiyaku((after_text_path).read_text(encoding="utf-8").splitlines())
    scores = {}
    for a in draft.amendments:
        if a.kind == "削除":
            continue
        number = normalize_article_ref(a.article)
        official = [x for x in after.articles if x.number == number]
        if not official:
            continue
        best = max(SequenceMatcher(None, _squash(a.text), _squash(o.text().split("\n", 1)[-1] if o.caption else o.text())).ratio()
                   for o in official)
        scores[a.article] = round(best, 3)
    avg = round(sum(scores.values()) / len(scores), 3) if scores else None
    return {"平均": avg, "条ごと": scores}


def main() -> None:
    review_path = sys.argv[1] if len(sys.argv) > 1 else latest_review()
    review = json.loads(open(review_path, encoding="utf-8").read())["result"]
    findings = [Finding(**{k: v for k, v in f.items()}) for f in review["findings"]]
    input_path = ROOT / review.get("input", "evals/data/r7_tantou_before.txt")
    info = review.get("basic_info", BASIC_INFO)
    kiyaku = load_kiyaku(input_path)
    is_standard = input_path.name == "r7_tantou_before.txt"
    print(f"指摘 {len(findings)}件（{review_path}）から改定案を作ります", flush=True)

    def progress(kind: str, text: str) -> None:
        if kind in ("session", "grading", "graded", "error"):
            print(f"  [{kind}] {text}", flush=True)
        elif kind == "tool" and text == "check_draft":
            print("  [tool] check_draft", flush=True)

    result = run_draft(kiyaku, findings, info, on_event=progress, title=f"評価：改定案の作成（{input_path.name}）")
    stamp = datetime.now(JST).strftime("%Y%m%d-%H%M")
    out = RESULTS / "drafts" / (stamp if is_standard else f"{stamp}-{input_path.stem}")
    out.mkdir(parents=True, exist_ok=True)

    required = sorted({f.topic_id for f in findings if f.category == "必須"})
    metrics = {
        "点検結果": str(review_path).replace(str(ROOT) + "/", ""),
        "入力": str(input_path.relative_to(ROOT)),
        "検査エラー": len(result.errors),
        "注意": result.warnings,
        "採点役の結果": [e["result"] for e in result.evaluations],
        "改定の数": len(result.draft.amendments) if result.draft else 0,
        "所要時間(秒)": round(result.elapsed_sec, 1),
        "費用": result.usage.get("list_cost"),
        "終了理由": result.stop,
        "セッション": result.session_id,
    }
    if result.draft:
        covered = {t for a in result.draft.amendments for t in a.finding_refs}
        metrics["必須の論点への対応"] = f"{len([t for t in required if t in covered])}/{len(required)}"
        metrics["改定の内訳"] = {k: sum(1 for a in result.draft.amendments if a.kind == k) for k in ("改正", "新設", "削除")}
        if is_standard:
            metrics["国交省の改正後条文との近さ"] = closeness(result.draft, DATA / "r7_tantou_after.txt")
        (out / "kaitei.json").write_text(json.dumps(result.draft.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out / "taisho.html").write_text(to_html(result.draft, kiyaku, f"新旧対照表（評価用：{input_path.name}）"), encoding="utf-8")
        (out / "taisho.md").write_text(to_markdown(result.draft, kiyaku, f"新旧対照表（評価用：{input_path.name}）"), encoding="utf-8")
    (out / "metrics.json").write_text(json.dumps({"metrics": metrics, "result": result.to_dict()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"保存: {out.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
