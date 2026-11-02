"""改定案から理事会の検討資料を作る。

入力：改定案のフォルダ（evals/results/drafts/<日時>/、kaitei.json があるところ）
出力：同じフォルダに board.html、board.json、board_metrics.json

使い方:  uv run python -m evals.run_board evals/results/drafts/<日時>
"""

from __future__ import annotations

import json
import sys
import time

from core.board import TIERS, coverage, generate, to_html
from core.config import ROOT
from core.draft import Amendment, Draft
from evals.run_eval import BASIC_INFO


def main() -> None:
    folder = (ROOT / sys.argv[1]).resolve()
    data = json.loads((folder / "kaitei.json").read_text(encoding="utf-8"))
    draft = Draft(amendments=[Amendment(**a) for a in data["amendments"]], notes=data["notes"])
    info = BASIC_INFO
    metrics_path = folder / "metrics.json"
    if metrics_path.exists():
        review_path = json.loads(metrics_path.read_text(encoding="utf-8"))["metrics"].get("点検結果")
        if review_path:
            info = json.loads((ROOT / review_path).read_text(encoding="utf-8"))["result"].get("basic_info", BASIC_INFO)
    print(f"改定案 {len(draft.amendments)}条（{folder.relative_to(ROOT)}）から理事会の検討資料を作ります", flush=True)

    started = time.monotonic()
    paper, usage = generate(draft, info)
    metrics = {
        "議題の数": len(paper.items),
        "段ごとの議題数": {t: sum(1 for i in paper.items if i.tier == t) for t in TIERS},
        "議題に入っていない改定": coverage(paper, draft),
        "所要時間(秒)": round(time.monotonic() - started, 1),
        "トークン": {k: usage.get(k) for k in ("input_tokens", "output_tokens")},
    }
    (folder / "board.json").write_text(paper.model_dump_json(indent=2), encoding="utf-8")
    (folder / "board.html").write_text(to_html(paper, None, f"評価用：{folder.name}"), encoding="utf-8")
    (folder / "board_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    for it in paper.items:
        print(f"  {it.tier[:4]}｜{it.title}｜{'、'.join(it.articles)}")
    print(f"保存: {(folder / 'board.html').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
