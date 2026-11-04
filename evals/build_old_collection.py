"""試験用の「規約集」（架空）を作る：古い規約＋細則3種＋改正履歴＋作業メモ。

evals/data/old_style_kiyaku.txt（evals/build_old_style.py で作る架空の規約）に、架空の細則を加える。
細則には、ツールが見つけるべき問題をあらかじめ仕込み、正解として記録する。問題のない細則も1つ入れて、
問題のない箇所を誤って指摘しないかも確かめる。実在のマンションとは関係ない。

出力（evals/data/）:
  old_collection.txt       … 試験用の規約集（点検の入力）
  old_collection_gold.json … 仕込んだ問題（文書・条・内容）と、問題のない細則
"""

from __future__ import annotations

import json

from core.config import ROOT
from core.ingest import load_collection

DATA = ROOT / "evals/data"

COVER = """○○マンション　管理規約・細則
（試験用・架空の規約集。実在のマンションとは関係ありません）
- 反映範囲 = 第25期定期総会 改正まで
- 注記の無い条は、規約原本の記載がそのまま有効です。
"""

MEETING_RULES = """○○マンション総会運営細則  （規約集 p40）
第1条（目的）  （規約集 p40）
この細則は、規約に基づき、総会の運営に関し必要な事項を定める。
第2条（議長）
総会の議長は、理事長が務める。
第3条（招集の特例）
緊急を要する場合には、理事長は、理事会の承認を得て、会議を開く日の5日前までに招集の通知を発することができる。
第4条（書面による議決権の行使）
書面により議決権を行使する組合員は、総会の開催日の前日までに議決権行使書を理事長に提出しなければならない。
第5条（規約の変更の決議）
規約の変更は、組合員総数の4分の3以上及び議決権総数の4分の3以上で決する。
第6条（細則の改廃）
この細則の変更又は廃止は、総会の決議による。
"""

PARKING_RULES = """○○マンション駐車場使用細則  （規約集 p42-p43）
第1条（目的）  （規約集 p42）
この細則は、規約第16条（駐車場の使用）に基づき、駐車場の使用に関し必要な事項を定める。
第2条（使用者の資格）
駐車場を使用できる者は、区分所有者及びその同居人とする。
第3条（使用料）
使用料は、月額8,000円とし、毎月末日までに翌月分を支払うものとする。
第4条（細則の改廃）
この細則の変更又は廃止は、総会の決議による。
"""

PET_RULES = """○○マンションペット飼育細則  （規約集 p45）
1. 飼育できる動物  （規約集 p45）
規約第19条ただし書に定める小鳥及び観賞用の魚類とする。
2. 飼育者の遵守事項
(1)　鳴き声等で他の居住者に迷惑をかけないこと。
(2)　共用部分では、かごや水槽から出さないこと。
3. 細則の改廃
この細則の変更又は廃止は、総会の決議による。
"""

HISTORY = """細則の改正履歴（判明している範囲）
第18期定期総会　駐車場使用細則の使用料を改定
第22期定期総会　ペット飼育細則を制定
"""

# 仕込んだ問題：(文書の題名の一部, 条, 内容, 種類)
PLANTED = [
    {"document": "総会運営細則", "article": "3", "issue": "緊急時の招集期間を5日前までに短縮できる（改正法第35条第1項は1週間前。規約で伸ばすことしかできない）",
     "kind": "改正法との食い違い"},
    {"document": "総会運営細則", "article": "5", "issue": "規約の変更の決議要件を細則で定め、しかも全員を母数にした4分の3（改正法第31条第1項と食い違い、規約で定めるべき事項）",
     "kind": "改正法との食い違い・規約で定めるべき事項"},
    {"document": "駐車場使用細則", "article": "1", "issue": "規約の駐車場の条を第16条と参照しているが、規約の駐車場の使用は第15条",
     "kind": "規約との食い違い"},
]
CLEAN = ["ペット飼育細則"]  # 問題を仕込んでいない細則（ここへの指摘は誤り）


def main() -> None:
    body = (DATA / "old_style_kiyaku.txt").read_text(encoding="utf-8")
    text = "\n".join([COVER, body, MEETING_RULES, PARKING_RULES, PET_RULES, HISTORY])
    (DATA / "old_collection.txt").write_text(text, encoding="utf-8")

    c = load_collection(DATA / "old_collection.txt")
    docs = c.summary()
    gold = {
        "source": "evals/data/old_style_kiyaku.txt に架空の細則を加えたもの（evals/build_old_collection.py）。実在のマンションとは関係ない",
        "documents": docs,
        "planted": PLANTED,
        "clean_rules": CLEAN,
        "required": json.loads((DATA / "old_style_gold.json").read_text(encoding="utf-8"))["required"],
    }
    (DATA / "old_collection_gold.json").write_text(json.dumps(gold, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for d in docs:
        print(f"{d['kind']}｜{d['title']}｜{d['articles']}{'項目' if d['style'] == '項目' else '条'}｜注記 {d['annotations']}")


if __name__ == "__main__":
    main()
