"""実物の規約で使った結果を数字だけでまとめる（scripts/usage_report.py）。API は呼ばない。"""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("usage_report", ROOT / "scripts/usage_report.py")
ur = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ur)


def _persona():
    d = sorted((ROOT / "data/public/persona_works").iterdir())[0]
    return d.name, json.loads((d / "work.json").read_text(encoding="utf-8"))


def test_numbers_only_no_text():
    wid, w = _persona()
    text = ur.render(ur.collect(w), wid)
    assert "指摘の数" in text and "採用の割合" in text and "人が記録すること" in text
    # 規約の文・作業の名前・管理組合の名前・委員会のメモは出さない
    leaks = [f["current_excerpt"][:15] for f in w["findings"] if f.get("current_excerpt")]
    leaks += [w.get("name", ""), w.get("org", "")]
    leaks += [e.get("note", "")[:15] for e in (w.get("human_edits") or {}).values() if e.get("note")]
    for s in leaks:
        if s and len(s) >= 4:
            assert s not in text, s


def test_counts_match_record():
    _, w = _persona()
    st = ur.collect(w)
    assert st["点検（AI）"]["指摘の数"] == len(w["findings"])
    assert st["改定案"]["改定の数"] == len(w["draft"]["amendments"])
    judged = st["指摘の判断（委員会）"]
    assert judged["採用"] + judged["不採用"] + judged["保留（あとで決める）"] == judged["判断した指摘（推奨・参考）"]
    assert st["AI の費用（ドル）"]["合計"] > 0
