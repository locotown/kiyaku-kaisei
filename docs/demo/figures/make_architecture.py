"""デモ動画の構成図（src/03_architecture.html）を作る。箱の位置と矢印を計算するため、手書きせずに生成する。

使い方: python3 docs/demo/figures/make_architecture.py && node docs/demo/figures/render.js
"""

from pathlib import Path

COLS = ["読み込み", "点検", "指摘の判断", "改定案", "理事会・住民", "総会のあと"]
X0, CW = 330, 241.6  # 列の左端と幅
LH, BW, BH = 162, 214, 124  # レーンの高さ、箱の幅と高さ
LANES = {  # 上端の y、名前、補足、英語、色
    "H": (268, "人", "委員会・理事会<br>総会", "People", "orange"),
    "C": (442, "Claude", "判断が要るところ", "AI", "blue"),
    "P": (616, "プログラム", "毎回同じ結果", "Code", "gray"),
}
BOXES = [
    ("P0", 0, "P", "規約を読み込む", "条・項に分ける（Word・PDF）"),
    ("C1", 1, "C", "点検役", "条を1つずつ取り寄せ、標準管理規約・法律と照合"),
    ("H2", 2, "H", "委員会が判断", "採用・保留・不採用"),
    ("C3", 3, "C", "書く役と採点役", "採点役が11の基準で確認し、合格まで直す"),
    ("P3", 3, "P", "自己点検", "条番号・参照・数値"),
    ("H4", 4, "H", "理事会が検討", "組合が選ぶ点を選ぶ"),
    ("C4", 4, "C", "資料と説明文", "理事会の資料・住民向けの説明"),
    ("H5", 5, "H", "総会で決議", "特別決議・普通決議"),
    ("P5", 5, "P", "最新の規約", "可決した改定を重ねる（AIなし）"),
]


def cx(i: int) -> float:
    return X0 + CW * (i + 0.5)


pos = {k: (cx(c) - BW / 2, LANES[lane][0] + (LH - BH) / 2) for k, c, lane, *_ in BOXES}
R = lambda k: (pos[k][0] + BW, pos[k][1] + BH / 2)
L = lambda k: (pos[k][0], pos[k][1] + BH / 2)
T = lambda k: (pos[k][0] + BW / 2, pos[k][1])
B = lambda k: (pos[k][0] + BW / 2, pos[k][1] + BH)


def curve(a, b):
    (x1, y1), (x2, y2) = a, b
    m = (x2 - x1) * 0.6
    return f'<path d="M{x1:.0f},{y1:.0f} C{x1 + m:.0f},{y1:.0f} {x2 - m:.0f},{y2:.0f} {x2 - 8:.0f},{y2:.0f}" marker-end="url(#a)"/>'


def down(a, b, both=False):
    (x1, y1), (_, y2) = a, b
    start = ' marker-start="url(#a)"' if both else ""
    return f'<path d="M{x1:.0f},{y1 + (8 if both else 0):.0f} L{x1:.0f},{y2 - 8:.0f}" marker-end="url(#a)"{start}/>'


paths = [curve(R("P0"), L("C1")), curve(R("C1"), L("H2")), curve(R("H2"), L("C3")), down(B("C3"), T("P3"), both=True),
         curve(R("C3"), L("H4")), down(B("H4"), T("C4")), curve(R("C4"), L("H5")), down(B("H5"), T("P5"))]
boxes = "".join(f'<div class="box b-{LANES[lane][4]}" style="left:{pos[k][0]:.0f}px;top:{pos[k][1]:.0f}px"><b>{t}</b><span>{s}</span></div>'
                for k, c, lane, t, s in BOXES)
lanes = "".join(f'<div class="lane l-{col}" style="top:{y}px;height:{LH}px"></div>'
                f'<div class="lname" style="top:{y}px;height:{LH}px"><b>{name}</b><span>{sub}</span><i>{en}</i></div>'
                for y, name, sub, en, col in LANES.values())
heads = "".join(f'<div class="col" style="left:{cx(i) - CW / 2:.0f}px;width:{CW:.0f}px">{c}</div>' for i, c in enumerate(COLS))

doc = f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><link rel="stylesheet" href="common.css">
<!-- make_architecture.py で生成。直接編集しない -->
<style>
body {{ padding-top: 64px; }}
h1 {{ font-size: 54px; }} .en {{ font-size: 26px; margin-top: 6px; }}
.lane {{ position: absolute; left: 140px; right: 140px; border-radius: 10px; }}
.l-orange {{ background: var(--orange-wash); }} .l-blue {{ background: var(--blue-wash); }} .l-gray {{ background: var(--gray-wash); }}
.lname {{ position: absolute; left: 160px; width: 175px; display: flex; flex-direction: column; justify-content: center; }}
.lname b {{ font-size: 30px; font-weight: 900; }} .lname span {{ font-size: 18px; color: var(--ink2); }} .lname i {{ font-style: normal; font-size: 18px; color: var(--muted); }}
.col {{ position: absolute; top: 228px; text-align: center; font-size: 22px; font-weight: 700; color: var(--ink2); }}
.box {{ position: absolute; width: {BW}px; height: {BH}px; background: #fff; border: 3px solid; border-radius: 10px; padding: 10px 12px;
        display: flex; flex-direction: column; justify-content: center; text-align: center; }}
.box b {{ font-size: 24px; font-weight: 900; line-height: 1.3; white-space: nowrap; }}
.box span {{ font-size: 17px; color: var(--ink2); line-height: 1.45; margin-top: 4px; }}
.b-orange {{ border-color: var(--orange); }} .b-blue {{ border-color: var(--blue); }} .b-gray {{ border-color: var(--gray); }}
svg {{ position: absolute; left: 0; top: 0; }} path {{ fill: none; stroke: var(--ink2); stroke-width: 3; }}
.foot {{ position: absolute; left: 140px; right: 140px; top: 796px; font-size: 21px; color: var(--ink2); line-height: 1.5; }}
.foot b {{ color: var(--blue); }}
</style></head><body>
<h1>判断は Claude に。正確さが要るところはプログラムに</h1>
<div class="en">Judgment goes to Claude. Anything that must be exact goes to plain code. People decide.</div>
{heads}
{lanes}
<svg width="1920" height="1080" viewBox="0 0 1920 1080"><defs><marker id="a" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" style="fill:var(--ink2);stroke:none"/></marker></defs>{"".join(paths)}</svg>
{boxes}
<div class="foot"><b>Claude</b>：点検と改定案は Managed Agents（改正の知識はスキルとして持たせ、規約の条はツールで1つずつ渡す。改定案は Outcomes の採点役が確認）。理事会の資料と住民向けの説明は Messages API。</div>
</body></html>
'''
(Path(__file__).parent / "src/03_architecture.html").write_text(doc, encoding="utf-8")
