"""検証ループ L2：採点役の差し戻し理由と自己点検のエラーを集計し、「よくある誤り」の候補を出す。

材料：
  - evals/results/drafts/*/metrics.json（公開の評価で作った改定案）
  - private/work/*/work.json（画面で作った改定案。非公開。手元でだけ集計する）

出力：
  - 画面：確認項目ごとの差し戻しの件数（数字だけ）
  - private/lessons/<日時>.md：差し戻し理由の抜粋つきの報告（実在の規約の文が混じりうるので、コミットしない）

使い方:  uv run python -m evals.lessons

候補を「よくある誤り」として採用する手順（docs/plans/検証ループ.md）：
  1. 報告を読み、繰り返している誤りの「型」を、実在の規約の文を含めずに書く
  2. 人が承認したら、skills/kiyaku-kaisei/SKILL.md の「よくある誤り（検証ループ）」に足し、uv run python -m agents.setup で反映する
  3. 評価（evals.run_draft）を回し、合格までの回数・費用が悪くならないことを確かめる。悪くなったら戻す
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime

from core.config import ROOT
from core.quality import RUBRIC_PLAIN
from core.review import JST

BAD = re.compile(r"満たしていない|満たさない|満たしていません|問題が(?:あ|残)|不備|合わない|合っていない|合いません|残って|違反|誤り|範囲外|欠番|照合ができ|partially")
HEADINGS = re.compile(r"問題点[：:]|【満たしていない点[^】]*】|【満たしている項目】|満たしている点[：:]")
ITEM = re.compile(r"項目\s*(\d{1,2})(?![〜~0-9])|^\s*\((\d{1,2})\)", re.MULTILINE)


def failed_items(explanation: str) -> dict[int, list[str]]:
    """差し戻しのコメントから、満たしていない確認項目の番号と、その理由の文を取り出す。"""
    out: dict[int, list[str]] = defaultdict(list)
    # 「(4) …」「項目4：…」ごとの塊に分け、否定の言葉を含む塊だけを数える
    chunks = re.split(r"(?=^\s*\(\d{1,2}\)|^\s*-\s*項目\d|項目\d{1,2}[：:（(])", explanation, flags=re.MULTILINE)
    for c in chunks:
        c = HEADINGS.sub("", c)  # 見出しの言葉（「問題点：」など）は数えない
        if re.search(r"not fully met|partially met|満点にはでき", c):  # 冒頭のまとめ（理由は後ろの項目ごとに書かれる）
            continue
        if not BAD.search(c):
            continue
        m = ITEM.search(c)
        if m:
            n = int(m.group(1) or m.group(2))
            if 1 <= n <= len(RUBRIC_PLAIN):
                out[n].append(" ".join(c.split())[:240])
    return out


def _check_kind(message: str) -> str:
    """自己点検のエラー・注意を、条番号などを除いた「型」にする。"""
    return re.sub(r"第[0-9０-９]+条(の[0-9]+)*|[0-9０-９]+", "○", message)[:60]


def collect() -> dict:
    runs = []
    for p in sorted((ROOT / "evals/results/drafts").glob("*/metrics.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        r = d.get("result", {})
        runs.append({"name": p.parent.name, "public": True, "evaluations": r.get("evaluations", []), "checks": r.get("checks", [])})
    for p in sorted((ROOT / "private/work").glob("*/work.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("draft_evaluations"):
            runs.append({"name": p.parent.name, "public": False, "evaluations": d["draft_evaluations"],
                         "checks": d.get("draft_checks", [])})
    # 同じ改定案を複製した作業（デモ用のコピーなど）は1件と数える
    uniq, keys = [], set()
    for r in runs:
        key = tuple((e.get("result"), (e.get("explanation") or "")[:400]) for e in r["evaluations"])
        if key not in keys:
            keys.add(key)
            uniq.append(r)
    runs = uniq
    items: Counter = Counter()
    reasons: dict[int, list[tuple[str, str]]] = defaultdict(list)
    checks: Counter = Counter()
    first_pass = sum(1 for r in runs if r["evaluations"] and r["evaluations"][0].get("result") == "satisfied")
    for r in runs:
        seen = set()
        for e in r["evaluations"]:
            if e.get("result") == "satisfied":
                continue
            for n, texts in failed_items(e.get("explanation") or "").items():
                seen.add(n)
                reasons[n] += [(r["name"], t) for t in texts[:2]]
        items.update(seen)  # 1つの改定案で同じ項目は1回と数える
        for c in r["checks"]:
            checks.update({_check_kind(x) for x in c.get("errors", []) + c.get("warnings", [])})
    return {"runs": runs, "items": items, "reasons": reasons, "checks": checks, "first_pass": first_pass}


def main() -> None:
    data = collect()
    runs = [r for r in data["runs"] if r["evaluations"]]
    print(f"改定案 {len(runs)}件（公開の評価 {sum(r['public'] for r in runs)}件・画面 {sum(not r['public'] for r in runs)}件）"
          f"／1回目で合格 {data['first_pass']}件")
    print("差し戻しの多い確認項目（1つの改定案で1回と数える）:")
    for n, c in data["items"].most_common():
        print(f"  項目{n}（{RUBRIC_PLAIN[n - 1]}）：{c}件")
    if data["checks"]:
        print("自己点検でよく出るエラー・注意の型:")
        for k, c in data["checks"].most_common(8):
            print(f"  {k}：{c}回")
    out = ROOT / "private/lessons"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{datetime.now(JST):%Y%m%d-%H%M}.md"
    lines = ["# よくある誤りの候補（非公開。実在の規約の文が混じりうるのでコミットしない）", ""]
    for n, c in data["items"].most_common():
        lines += [f"## 項目{n}：{RUBRIC_PLAIN[n - 1]}（{c}件）", ""]
        lines += [f"- {name}：{t}" for name, t in data["reasons"][n][:8]] + [""]
    path.write_text("\n".join(lines), encoding="utf-8")
    print("報告:", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
