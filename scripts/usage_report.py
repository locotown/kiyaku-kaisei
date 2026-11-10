"""実物の規約で使った結果を、数字だけでまとめる（11/10 作者の判断：審査で「実際に使った結果の数字がない」と分かったため）。

使い方（作者の Mac で、実物の作業に対して）:
    uv run python scripts/usage_report.py               # 作業の一覧（ID と名前）
    uv run python scripts/usage_report.py <作業ID>      # その作業の数字（private/reports/<作業ID>.md にも保存）

- 出すのは数字だけ。規約の文・マンション名・作業の名前・人の名前は出さない
  （作業の一覧を出すときだけ、作業を選べるように名前を画面に出す。ファイルには書かない）
- 保存先 private/reports/ はコミットしない（.gitignore の private/）
- AI だけでは分からない数字（委員会でかかった時間、専門家に頼んだときの見積もり、AI の誤りに気づいた数）は、
  出力の「人が記録すること」の欄に書き足す
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import store  # noqa: E402
from core.auth import _usd  # noqa: E402

REPORTS = store.DATA / "reports"


def _work_dirs() -> list[Path]:
    return sorted(p.parent for p in store.WORK.glob("*/work.json")) if store.WORK.exists() else []


def _load(work_id: str) -> dict:
    p = store.WORK / work_id / "work.json"
    if not p.exists():   # 架空の想定ユーザーの作業（確かめ用）も読めるように
        p = ROOT / "data/public/persona_works" / work_id / "work.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _pct(a: int, b: int) -> str:
    return f"{a / b * 100:.0f}%" if b else "—"


def _minutes(sec: float | None) -> str:
    return f"{sec / 60:.1f}分" if sec else "—"


def collect(w: dict) -> dict:
    """作業の記録から数字だけを取り出す（文は取り出さない）。"""
    findings = w.get("findings") or []
    cats = Counter(f.get("category", "") for f in findings)
    decisions = w.get("decisions") or {}
    judged = [decisions.get(str(i), {}).get("decision", "保留") for i, f in enumerate(findings) if f.get("category") != "必須"]
    dec = Counter(judged)
    with_reason = sum(1 for i, f in enumerate(findings) if f.get("category") != "必須"
                      and (decisions.get(str(i), {}).get("reason") or "").strip())
    draft = w.get("draft") or {}
    amends = draft.get("amendments") or [] if isinstance(draft, dict) else []
    kinds = Counter(a.get("kind", "") for a in amends)
    evals = w.get("draft_evaluations") or []
    edits = w.get("human_edits") or {}
    verdicts = Counter((e.get("review") or {}).get("verdict", "確認なし") for e in edits.values() if isinstance(e, dict))
    board = Counter(v.get("decision", "") for v in (w.get("board_decisions") or {}).values())
    notes = [n for n in (w.get("notes") or []) if isinstance(n, dict)]
    photos = sum(len(n.get("photos") or []) for n in notes)
    proposals = sum(len(n.get("proposals") or []) for n in notes)
    meeting = w.get("meeting") or {}
    results = Counter((meeting.get("results") or {}).values())
    costs = w.get("costs") or []
    cost_by_step = Counter()
    for c in costs:
        step = str(c.get("step", "")).split("（")[0]
        cost_by_step[step] += _usd(c)
    cost_notes = sum(float(n.get("cost_usd") or 0) for n in notes)
    log = [e for e in (w.get("log") or []) if isinstance(e, dict) and e.get("ts")]
    docs = w.get("documents") or []
    return {
        "規約の規模": {
            "読み込んだ文書の数": len([d for d in docs if d.get("kind") != "メモ"]) or 1,
            "規約の条の数": w.get("articles") if isinstance(w.get("articles"), int) else len(w.get("articles") or []),
            "細則の数": sum(1 for d in docs if d.get("kind") == "細則"),
        },
        "点検（AI）": {
            "指摘の数": len(findings),
            "必須": cats.get("必須", 0), "推奨": cats.get("推奨", 0), "参考": cats.get("参考", 0),
            "作業の記録の最初から最後まで（人が考えた時間を含む）": _minutes(log[-1]["ts"] - log[0]["ts"] if len(log) > 1 else None),
        },
        "指摘の判断（委員会）": {
            "判断した指摘（推奨・参考）": len(judged),
            "採用": dec.get("採用", 0), "不採用": dec.get("不採用", 0), "保留（あとで決める）": dec.get("保留", 0),
            "採用の割合": _pct(dec.get("採用", 0), len(judged)),
            "理由を書いた判断": with_reason,
        },
        "改定案": {
            "改定の数": len(amends),
            "改正": kinds.get("改正", 0), "新設": kinds.get("新設", 0), "削除": kinds.get("削除", 0),
            "確認役の採点の回数": len(evals),
            "作成にかかった時間": _minutes(w.get("draft_elapsed")),
        },
        "委員会で直した文": {
            "直した条の数": len(edits),
            "AI の確認：問題なし": verdicts.get("問題なし", 0),
            "AI の確認：気になる点あり": verdicts.get("気になる点あり", 0),
            "AI の確認をしていない": verdicts.get("確認なし", 0),
        },
        "理事会の検討": dict(board) or {"判断": 0},
        "写真の書き込み": {"読み込んだ回数": len(notes), "写真の枚数": photos, "読み取った直しの案": proposals},
        "総会": {"結果を記録した文書": sum(results.values()), **dict(results),
                 "総会で直した条": len(meeting.get("edits") or {})},
        "AI の費用（ドル）": {**{k: round(v, 2) for k, v in cost_by_step.items()},
                          **({"写真の読み取り": round(cost_notes, 2)} if cost_notes else {}),
                          "合計": round(sum(cost_by_step.values()) + cost_notes, 2)},
    }


MANUAL = """## 人が記録すること（AI では分からない数字）

| 項目 | 記入 |
| --- | --- |
| 委員会・理事会で、このツールを使って見直しにかけた時間（合計） | |
| ツールなしで同じ見直しをした場合の見込み時間（前回の改正の実績など） | |
| 専門家（マンション管理士・弁護士）に頼んだ場合の見積もり額 | |
| AI の指摘のうち、誤りだと委員会が判断した数 | |
| AI の改定案・説明で、委員会が直した誤り（法律の読み違いなど）の数 | |
| 住民からの質問・反対の数（説明を配ったあと） | |
| 委員の感想（一言） | |
"""


def render(stats: dict, work_id: str) -> str:
    out = [f"# 実物の規約で使った結果（作業 {work_id}）", "",
           "数字だけを記録しています。規約の文・マンション名・人の名前は入れていません。", ""]
    for sec, kv in stats.items():
        out.append(f"## {sec}")
        out.append("")
        out.append("| 項目 | 数 |")
        out.append("| --- | --- |")
        for k, v in kv.items():
            out.append(f"| {k} | {v} |")
        out.append("")
    out.append(MANUAL)
    return "\n".join(out)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        dirs = _work_dirs()
        if not dirs:
            print("作業がありません（private/work/）。")
            return 1
        print("作業の一覧（この画面にだけ出します）：")
        for d in dirs:
            try:
                w = json.loads((d / "work.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            print(f"  {d.name}\t{w.get('status', '')}\t{w.get('name', '')}")
        print("\nuv run python scripts/usage_report.py <作業ID> で数字をまとめます。")
        return 0
    work_id = argv[1]
    text = render(collect(_load(work_id)), work_id)
    print(text)
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"{work_id}.md").write_text(text, encoding="utf-8")
    print(f"\n保存しました：{REPORTS / (work_id + '.md')}（コミットしません）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
