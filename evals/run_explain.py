"""住民向け説明文を作り、読みやすさの目安を測る。

入力：改定案（evals/results/drafts/<日時>/kaitei.json。省略時は最新）
出力：同じフォルダに explain.html、explain.json、explain_metrics.json
読みやすさの評価の本体は、担当者による5段階評価（docs/SPEC.md）。ここで出す数値は判断の目安。

使い方:  uv run python -m evals.run_explain [改定案のフォルダ]
"""

from __future__ import annotations

import json
import sys
import time

from core.config import ROOT
from core.draft import Amendment, Draft
from core.explain import TIERS, coverage, generate, to_html
from core.readability import measure_explanation
from evals.run_eval import BASIC_INFO

DRAFTS = ROOT / "evals/results/drafts"


def main() -> None:
    folder = (ROOT / sys.argv[1]).resolve() if len(sys.argv) > 1 else sorted(p for p in DRAFTS.iterdir() if p.is_dir())[-1]
    data = json.loads((folder / "kaitei.json").read_text(encoding="utf-8"))
    draft = Draft(amendments=[Amendment(**a) for a in data["amendments"]], notes=data["notes"])
    print(f"改定案 {len(draft.amendments)}条（{folder.relative_to(ROOT)}）から説明文を作ります", flush=True)

    started = time.monotonic()
    metrics_path = folder / "metrics.json"
    info = BASIC_INFO
    if metrics_path.exists():
        review_path = json.loads(metrics_path.read_text(encoding="utf-8"))["metrics"].get("点検結果")
        if review_path:
            info = json.loads((ROOT / review_path).read_text(encoding="utf-8"))["result"].get("basic_info", BASIC_INFO)
    ex, usage = generate(draft, info)
    elapsed = round(time.monotonic() - started, 1)
    metrics = {
        "項目の数": len(ex.items),
        "法律の改正に合わせる項目": sum(1 for i in ex.items if i.required),
        "段ごとの項目数": {t: sum(1 for i in ex.items if i.tier == t) for t in TIERS},
        "本文で取り上げていない改定": coverage(ex, draft)["missing"],
        "意見を伺いたい点": len(ex.choices),
        "読みやすさの目安": measure_explanation(ex),
        "所要時間(秒)": elapsed,
        "トークン": {k: usage.get(k) for k in ("input_tokens", "output_tokens")},
    }
    (folder / "explain.json").write_text(ex.model_dump_json(indent=2), encoding="utf-8")
    (folder / "explain.html").write_text(to_html(ex, f"評価用：{folder.name}", draft), encoding="utf-8")
    (folder / "explain_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"保存: {(folder / 'explain.html').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
