"""判断の履歴のテスト。"""

from core.history import line, record


def test_record():
    h = record({"decision": "保留", "reason": ""}, "採用", "理事会で合意", "11月03日 10:00")
    assert h == [{"at": "11月03日 10:00", "from": "保留", "to": "採用", "reason": "理事会で合意"}]
    d = {"decision": "採用", "reason": "理事会で合意", "history": h}
    h2 = record(d, "採用", "理事会で合意（全員賛成）", "11月03日 10:05")  # 理由だけ直す → 最新を書き直す
    assert len(h2) == 1 and h2[0]["reason"] == "理事会で合意（全員賛成）" and h2[0]["edited_at"] == "11月03日 10:05"
    assert d["history"][0]["reason"] == "理事会で合意"  # 元の記録は変えない
    h3 = record({**d, "history": h2}, "不採用", "説明会で反対多数", "11月10日 21:00")
    assert [e["to"] for e in h3] == ["採用", "不採用"]
    assert record({"decision": "保留", "reason": ""}, "保留", "", "x") == []  # 何も変わらなければ追加しない
    h4 = record({"decision": "保留", "reason": ""}, "保留", "情報待ち", "x")  # 判断はそのまま理由だけ書く
    assert h4[0]["from"] == h4[0]["to"] == "保留"
    assert "保留（理由を記入）" in line(h4[0])
    assert line(h3[-1]) == "11月10日 21:00　採用 → 不採用　「説明会で反対多数」"


def test_board_extra():
    h = record({}, "採用", "", "t1", reason_key="note", extra={"choice": "（イ）案"})
    assert h[0]["choice"] == "（イ）案" and h[0]["from"] == ""
    h2 = record({"decision": "採用", "note": "", "choice": "（イ）案", "history": h}, "採用", "", "t2",
                reason_key="note", extra={"choice": "（ア）案"})
    assert len(h2) == 1 and h2[0]["choice"] == "（ア）案"
    assert "（初期） → 採用" in line(h[0])
