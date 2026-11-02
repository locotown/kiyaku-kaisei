"""改定案の確認結果の表示のテスト。"""

from core.quality import RUBRIC_PLAIN, draft_quality
from core.drafting import RUBRIC


def test_quality():
    work = {"draft": {"amendments": [{"document": "規約"}, {"document": "規約", "choices": ["ア", "イ"]},
                                     {"document": "○○マンション総会運営細則"}]},
            "draft_errors": [],
            "draft_evaluations": [{"result": "needs_revision", "explanation": "x"},
                                  {"result": "satisfied", "explanation": "An independent grader found all criteria met:\n- 項目 (met): ok"}]}
    q = draft_quality(work)
    assert q["level"] == "ok" and "2回目で合格" in q["head"] and q["checks_ok"]
    assert [r["result"] for r in q["rounds"]] == ["直しが必要", "合格"]
    assert q["rounds"][1]["explanation"].startswith("採点役のまとめ") and "（満たす）" in q["rounds"][1]["explanation"]
    assert q["by_doc"] == {"規約": 2, "○○マンション総会運営細則": 1} and q["choices"] == 1
    assert draft_quality({**work, "draft_evaluations": [{"result": "max_iterations_reached"}]})["level"] == "warn"
    assert draft_quality({**work, "draft_evaluations": []})["level"] == "warn"


def test_rubric_plain_matches_rubric():
    # 採点役の確認項目を変えたら、画面向けの言い換えも合わせて直す
    import re

    assert len(RUBRIC_PLAIN) == sum(1 for line in RUBRIC.splitlines() if re.match(r"^\d+\. ", line))
