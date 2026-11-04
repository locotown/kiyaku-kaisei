"""デモ動画のイラスト（src/05〜09）を作る。写真を撮るまでの仮のものには「仮」の印を付ける。

使い方: python3 docs/demo/figures/make_illustrations.py && node docs/demo/figures/render.js
すべて自作の図形（素材集・AI 画像は使っていない）。実在のマンションは描かない。
"""

from pathlib import Path

SRC = Path(__file__).parent / "src"
HEAD = '<!doctype html><html lang="ja"><head><meta charset="utf-8"><link rel="stylesheet" href="common.css"><style>body{{padding:0}}{css}</style></head><body>'
KARI = '<div class="kari">仮</div>'
FUTON = ["#eb6834", "#2a78d6", "#f3c26b", "#e87ba4", "#9cc5a1"]


def danchi(x, y, floors=5, units=8, scale=1.0, number="3", seed=0):
    """団地の1棟（バルコニー側）。ところどころに布団と洗濯物を干す。"""
    uw, fh = 76, 72
    w, h = units * uw + 40, floors * fh + 30
    out = [f'<g transform="translate({x},{y}) scale({scale})">',
           f'<rect x="0" y="0" width="{w}" height="{h}" fill="#f2efe6" stroke="#c9c4b5" stroke-width="2"/>',
           f'<rect x="-6" y="-10" width="{w + 12}" height="14" fill="#b9b3a3"/>',  # 屋上のふち
           f'<rect x="{w - 40}" y="0" width="40" height="{h}" fill="#e6e1d3"/>',  # 妻側の壁
           f'<text x="{w - 20}" y="70" font-size="44" font-weight="900" fill="#8f8a7c" text-anchor="middle">{number}</text>']
    k = seed
    for f in range(floors):
        fy = 18 + f * fh
        for u in range(units):
            ux = 12 + u * uw
            out.append(f'<rect x="{ux + 6}" y="{fy + 6}" width="{uw - 12}" height="{fh - 30}" fill="#9fb4c8" rx="2"/>')  # 窓
            out.append(f'<rect x="{ux + 6}" y="{fy + 6}" width="{(uw - 12) / 2}" height="{fh - 30}" fill="#b7c8d8" rx="2"/>')
            out.append(f'<rect x="{ux}" y="{fy + fh - 26}" width="{uw}" height="22" fill="#e9e5da" stroke="#c9c4b5"/>')  # バルコニーの手すり壁
            k = (k * 7 + 3) % 11
            if k in (1, 4):  # 布団を干す
                c = FUTON[(f + u + seed) % len(FUTON)]
                out.append(f'<rect x="{ux + 10}" y="{fy + fh - 34}" width="{uw - 20}" height="30" fill="{c}" rx="4"/>')
                out.append(f'<rect x="{ux + 10}" y="{fy + fh - 34}" width="{uw - 20}" height="6" fill="#ffffff" opacity=".35" rx="3"/>')
            elif k == 7:  # 洗濯物
                out.append(f'<line x1="{ux + 8}" y1="{fy + 14}" x2="{ux + uw - 8}" y2="{fy + 14}" stroke="#8f8a7c" stroke-width="2"/>')
                for j, c in enumerate(("#ffffff", "#2a78d6", "#f3c26b")):
                    out.append(f'<rect x="{ux + 12 + j * 18}" y="{fy + 15}" width="14" height="20" fill="{c}" stroke="#c9c4b5"/>')
    out.append("</g>")
    return "".join(out)


def tree(x, y, r=48, c="#6fae6d"):
    return (f'<rect x="{x - 5}" y="{y}" width="10" height="{r * .9}" fill="#8a6a4a"/>'
            f'<circle cx="{x}" cy="{y - r * .2}" r="{r}" fill="{c}"/><circle cx="{x - r * .6}" cy="{y + r * .15}" r="{r * .7}" fill="{c}"/>'
            f'<circle cx="{x + r * .6}" cy="{y + r * .1}" r="{r * .75}" fill="{c}"/>')


def landscape() -> str:
    svg = ['<svg width="1920" height="1080" viewBox="0 0 1920 1080">',
           '<defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#cfe2f6"/><stop offset="1" stop-color="#f6f8fb"/></linearGradient></defs>',
           '<rect width="1920" height="1080" fill="url(#sky)"/>',
           '<circle cx="1610" cy="170" r="70" fill="#fff6d8"/>']
    for x, w, h in ((40, 160, 360), (230, 120, 300), (1380, 150, 420), (1560, 200, 330), (1790, 140, 380), (820, 130, 260)):  # 遠くの高いマンション
        svg.append(f'<rect x="{x}" y="{700 - h}" width="{w}" height="{h}" fill="#c4d2df"/>')
        for fy in range(700 - h + 16, 690, 26):
            svg.append(f'<rect x="{x + 10}" y="{fy}" width="{w - 20}" height="6" fill="#b2c2d1"/>')
    svg.append(danchi(980, 360, floors=5, units=9, scale=.82, number="5", seed=2))
    svg.append(danchi(120, 330, floors=5, units=9, scale=.92, number="4", seed=5))
    svg.append('<rect x="0" y="760" width="1920" height="320" fill="#a9cf96"/>')
    svg.append(danchi(560, 420, floors=5, units=10, scale=1.05, number="3", seed=1))
    svg.append('<rect x="0" y="870" width="1920" height="210" fill="#c9c6bd"/><rect x="0" y="862" width="1920" height="12" fill="#e4e1d8"/>')
    for x in range(40, 1920, 160):
        svg.append(f'<rect x="{x}" y="960" width="80" height="8" fill="#f5f3ee"/>')
    for x, r, c in ((90, 60, "#5f9f5e"), (470, 52, "#6fae6d"), (1180, 46, "#5f9f5e"), (1480, 64, "#6fae6d"), (1760, 50, "#5f9f5e")):
        svg.append(tree(x, 800, r, c))
    # 電柱と電線（日本の住宅地らしさ）
    svg.append('<rect x="1660" y="300" width="16" height="580" fill="#8e8a80"/><rect x="1610" y="340" width="120" height="10" fill="#8e8a80"/><rect x="1625" y="380" width="90" height="8" fill="#8e8a80"/>')
    for dy in (345, 383):
        svg.append(f'<path d="M-20,{dy + 60} Q 820,{dy + 140} 1615,{dy}" stroke="#55524c" stroke-width="2" fill="none"/>')
        svg.append(f'<path d="M1725,{dy} Q 1830,{dy + 18} 1940,{dy + 10}" stroke="#55524c" stroke-width="2" fill="none"/>')
    svg.append("</svg>")
    return HEAD.format(css="") + "".join(svg) + KARI + "</body></html>"


def person(x, y, c, hand=False, s=1.0):
    """後ろ姿の住民（頭と肩）。hand=True なら手を挙げる。"""
    out = [f'<g transform="translate({x},{y}) scale({s})">']
    if hand:
        out.append(f'<rect x="22" y="-120" width="16" height="96" rx="8" fill="{c}"/><circle cx="30" cy="-124" r="12" fill="#f0c9a8"/>')
    out.append(f'<path d="M-46,60 Q-46,-10 0,-10 Q46,-10 46,60 Z" fill="{c}"/><circle cx="0" cy="-34" r="28" fill="#3b3a36"/>')
    out.append("</g>")
    return "".join(out)


def meeting() -> str:
    svg = ['<svg width="1920" height="1080" viewBox="0 0 1920 1080">',
           '<rect width="1920" height="1080" fill="#efe9dc"/>',  # 集会室の壁
           '<rect x="0" y="0" width="1920" height="70" fill="#e2dccd"/>',
           '<rect x="0" y="640" width="1920" height="440" fill="#c9b79a"/>',  # 床
           '<rect x="0" y="632" width="1920" height="10" fill="#b39f80"/>']
    for x in (120, 1560):  # 窓
        svg.append(f'<rect x="{x}" y="140" width="240" height="300" fill="#d9e8f5" stroke="#bfb5a2" stroke-width="10"/><line x1="{x + 120}" y1="140" x2="{x + 120}" y2="440" stroke="#bfb5a2" stroke-width="8"/>')
    svg.append('<rect x="560" y="110" width="800" height="300" fill="#ffffff" stroke="#bfb5a2" stroke-width="8" rx="6"/>')  # ホワイトボード
    svg.append('<text x="960" y="210" font-size="56" font-weight="900" text-anchor="middle" fill="#2b2a27">第25期 定期総会</text>')
    svg.append('<text x="960" y="282" font-size="34" font-weight="700" text-anchor="middle" fill="#52514e">第1号議案　管理規約の改定</text>')
    svg.append('<text x="960" y="340" font-size="26" text-anchor="middle" fill="#898781">さくら台マンション管理組合（架空）</text>')
    svg.append('<rect x="620" y="470" width="680" height="60" fill="#8f7a5d"/><rect x="640" y="530" width="20" height="110" fill="#6f5d45"/><rect x="1260" y="530" width="20" height="110" fill="#6f5d45"/>')  # 役員の長机
    for i, c in enumerate(("#2a78d6", "#52514e", "#eb6834")):  # 役員
        svg.append(f'<circle cx="{760 + i * 200}" cy="420" r="30" fill="#3b3a36"/><circle cx="{760 + i * 200}" cy="428" r="24" fill="#f0c9a8"/><path d="M{712 + i * 200},470 Q{712 + i * 200},450 {760 + i * 200},450 Q{808 + i * 200},450 {808 + i * 200},470 Z" fill="{c}"/>')
    svg.append('<rect x="700" y="482" width="70" height="40" fill="#ffffff"/><rect x="1150" y="482" width="70" height="40" fill="#ffffff"/>')  # 議案書
    svg.append('<rect x="905" y="478" width="110" height="34" fill="#ffffff" stroke="#c8102e" stroke-width="3"/><text x="960" y="503" font-size="20" font-weight="900" text-anchor="middle" fill="#c8102e">議長</text>')
    colors = ["#5b7fa6", "#8a8f6a", "#a66b5b", "#6a6f8a", "#7a8a8f", "#9a7a5a", "#5b8a7f"]
    for row, (yy, s) in enumerate(((790, 1.0), (930, 1.18))):  # 住民の列（長机とパイプ椅子）
        svg.append(f'<rect x="80" y="{yy - 66}" width="1760" height="26" fill="#d8d2c3"/>')
        for i in range(7):
            x = 200 + i * 250 + (60 if row else 0)
            svg.append(person(x, yy, colors[(i + row * 3) % 7], hand=(i + row) % 3 != 1, s=s))
    svg.append("</svg>")
    return HEAD.format(css="") + "".join(svg) + "</body></html>"


def law_paper() -> str:
    css = (".paper{position:absolute;left:460px;top:90px;width:1000px;height:760px;background:#fffdf7;box-shadow:0 12px 40px rgba(0,0,0,.12);padding:70px 80px}"
           ".paper h2{font-size:40px;font-weight:900;text-align:center;letter-spacing:.1em}.paper .sub{text-align:center;color:#52514e;font-size:24px;margin:10px 0 40px}"
           ".paper p{font-size:26px;line-height:1.9;color:#2b2a27;text-indent:1em}.paper .ln{height:14px;background:#e6e2d6;margin:20px 0;border-radius:3px}")
    # 条文は e-Gov の正文どおり（data/public/egov/kubun_shoyu_ho_20260401.json の第31条第1項前段）
    body = ('<div class="paper"><h2>建物の区分所有等に関する法律</h2><div class="sub">第三十一条第一項（2026年4月1日施行の条文から抜粋）</div>'
            '<p>規約の設定、変更又は廃止は、集会において、区分所有者（議決権を有しないものを除く。以下この項前段において同じ。）の過半数'
            '（これを上回る割合を規約で定めた場合にあつては、その割合以上）の者であつて議決権の過半数（これを上回る割合を規約で定めた場合にあつては、'
            'その割合以上）を有するものが出席し、出席した区分所有者及びその議決権の各四分の三以上の多数による決議によつてする。</p></div>')
    return HEAD.format(css=css) + body + "</body></html>"


def stamp(text_top: str, text_main: str, size=420) -> str:
    """朱肉の判子（背景は透明）。動画の編集で、押す動きを付けて重ねる。"""
    css = ("html,body{background:transparent!important}"
           f".st{{position:absolute;left:40px;top:40px;width:{size}px;height:{size}px;border:16px solid #c8102e;border-radius:50%;"
           "display:flex;flex-direction:column;align-items:center;justify-content:center;color:#c8102e;transform:rotate(-8deg);opacity:.92}"
           ".st .t{font-size:46px;font-weight:900;border-bottom:8px solid #c8102e;padding:0 20px 6px;letter-spacing:.06em}"
           ".st .m{font-size:120px;font-weight:900;line-height:1.2;letter-spacing:.08em}")
    return HEAD.format(css=css) + f'<div class="st"><div class="t">{text_top}</div><div class="m">{text_main}</div></div></body></html>'


def scaffold() -> str:
    svg = ['<svg width="1920" height="1080" viewBox="0 0 1920 1080">',
           '<defs><linearGradient id="sky2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#d6e6f5"/><stop offset="1" stop-color="#f6f8fb"/></linearGradient>'
           '<pattern id="mesh" width="14" height="14" patternUnits="userSpaceOnUse"><rect width="14" height="14" fill="#dfe5ea"/><path d="M0,7 H14 M7,0 V14" stroke="#c7d0d8" stroke-width="2"/></pattern></defs>',
           '<rect width="1920" height="1080" fill="url(#sky2)"/>',
           '<rect x="0" y="830" width="1920" height="250" fill="#c9c6bd"/>']
    x0, y0, w, h = 420, 120, 1080, 710  # 足場とメッシュシートで覆われた建物
    svg.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" fill="url(#mesh)"/>')
    for i in range(0, w + 1, 120):
        svg.append(f'<rect x="{x0 + i - 4}" y="{y0 - 20}" width="8" height="{h + 20}" fill="#7d8894"/>')
    for j in range(0, h + 1, 88):
        svg.append(f'<rect x="{x0 - 10}" y="{y0 + j - 4}" width="{w + 20}" height="8" fill="#7d8894"/>')
    svg.append(f'<rect x="{x0 + 330}" y="{y0 + 300}" width="420" height="150" fill="#ffffff" stroke="#2a78d6" stroke-width="6"/>')
    svg.append(f'<text x="{x0 + 540}" y="{y0 + 375}" font-size="46" font-weight="900" text-anchor="middle" fill="#1f5fae">大規模修繕工事</text>')
    svg.append(f'<text x="{x0 + 540}" y="{y0 + 425}" font-size="26" font-weight="700" text-anchor="middle" fill="#52514e">ご迷惑をおかけします</text>')
    svg.append('<rect x="150" y="560" width="200" height="270" fill="#f2efe6" stroke="#c9c4b5"/><rect x="1580" y="600" width="230" height="230" fill="#f2efe6" stroke="#c9c4b5"/>')
    svg.append('<rect x="1200" y="760" width="180" height="70" fill="#f3c26b"/><rect x="1215" y="740" width="70" height="30" fill="#f3c26b"/><circle cx="1240" cy="835" r="16" fill="#3b3a36"/><circle cx="1350" cy="835" r="16" fill="#3b3a36"/>')
    for x in range(200, 1760, 70):  # 工事中のバリケード
        svg.append(f'<rect x="{x}" y="850" width="56" height="44" fill="{"#f3c26b" if (x // 70) % 2 else "#3b3a36"}"/>')
    svg.append("</svg>")
    return HEAD.format(css="") + "".join(svg) + KARI + "</body></html>"


def keijiban() -> str:
    """マンションのエントランスの掲示板。規約の見直しのお知らせが貼られている（パターンC の冒頭）。"""
    def paper(x, y, w, h, title, lines, rot=0, color="#ffffff", pin="#c8102e", big=False):
        body = "".join(f'<div class="ln" style="width:{l}%"></div>' for l in lines)
        return (f'<div class="pp{" big" if big else ""}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;transform:rotate({rot}deg);background:{color}">'
                f'<i style="background:{pin}"></i><b>{title}</b>{body}</div>')
    css = (".wall{position:absolute;inset:0;background:#e9e3d6}.board{position:absolute;left:170px;top:90px;width:1580px;height:800px;"
           "background:#c49a6c;border:22px solid #7a5a3a;border-radius:10px;box-shadow:0 14px 40px rgba(0,0,0,.25)}"
           ".board::before{content:'掲示板';position:absolute;left:50%;top:-58px;transform:translateX(-50%);background:#7a5a3a;color:#fff;"
           "font-weight:900;font-size:34px;padding:4px 40px;border-radius:8px 8px 0 0;letter-spacing:.3em}"
           ".pp{position:absolute;padding:30px 26px 20px;box-shadow:0 6px 14px rgba(0,0,0,.2)}.pp i{position:absolute;left:50%;top:10px;width:18px;height:18px;border-radius:50%}"
           ".pp b{display:block;font-size:24px;font-weight:900;margin-bottom:16px;color:#2b2a27}.pp .ln{height:9px;background:#d9d4c7;border-radius:3px;margin:12px 0}"
           ".pp.big b{font-size:40px;line-height:1.35;margin-bottom:22px}.pp.big .ln{height:12px;margin:18px 0}"
           ".note{position:absolute;right:40px;top:30px;font-size:22px;color:#52514e}")
    body = ('<div class="wall"></div><div class="board">'
            + paper(70, 70, 330, 300, "ごみ出しのルール", [90, 80, 85, 60, 75], -3, "#fff8e1", "#2a78d6")
            + paper(80, 420, 320, 280, "夏祭りのお知らせ", [85, 70, 90, 55], 2, "#ffe9e0", "#1baf7a")
            + paper(480, 60, 640, 640, "お知らせ<br>区分所有法の改正に伴う<br>管理規約の見直しについて", [92, 88, 95, 70, 90, 84, 60], 0, "#ffffff", "#c8102e", True)
            + paper(1190, 80, 300, 320, "消防設備点検のお知らせ", [88, 75, 82, 60], 3, "#eef4fb", "#eda100")
            + paper(1200, 450, 290, 250, "駐輪場の整理", [80, 85, 60], -2, "#ffffff", "#2a78d6")
            + '</div><div class="note">※ 登場する人物・マンションは架空です</div>')
    return HEAD.format(css=css) + body + "</body></html>"


def rijicho() -> str:
    """食卓で、分厚い規約集と法律の条文を前に悩む理事長（後ろ姿。パターンC）。"""
    svg = ['<svg width="1920" height="1080" viewBox="0 0 1920 1080">',
           '<rect width="1920" height="1080" fill="#f3ede1"/>',
           '<rect x="1240" y="110" width="480" height="380" fill="#d9e8f5" stroke="#c4b49a" stroke-width="14"/>',  # 窓
           '<line x1="1480" y1="110" x2="1480" y2="490" stroke="#c4b49a" stroke-width="10"/>',
           '<circle cx="1610" cy="200" r="40" fill="#fff6d8"/>',
           '<rect x="0" y="620" width="1920" height="460" fill="#d8c3a0"/>',  # 床
           '<path d="M260,560 L1660,560 L1760,700 L160,700 Z" fill="#a9825a"/>',  # 食卓
           '<rect x="160" y="700" width="1600" height="26" fill="#8a6a4a"/>',
           '<rect x="230" y="726" width="26" height="300" fill="#7a5a3a"/><rect x="1664" y="726" width="26" height="300" fill="#7a5a3a"/>',
           # 分厚い規約集（ファイル）
           '<g transform="translate(640,430) rotate(-6)"><rect width="300" height="150" rx="6" fill="#2a5d9f"/><rect x="0" y="0" width="34" height="150" fill="#1f4778"/>'
           '<rect x="80" y="40" width="180" height="60" fill="#ffffff"/><text x="170" y="80" font-size="30" font-weight="900" text-anchor="middle" fill="#1f4778">管理規約集</text></g>',
           # 法律の条文の紙
           '<g transform="translate(1000,470) rotate(5)"><rect width="300" height="200" fill="#fffdf7" stroke="#d9d4c7"/>'
           '<text x="150" y="44" font-size="24" font-weight="900" text-anchor="middle" fill="#2b2a27">区分所有法</text>'
           + ''.join(f'<rect x="28" y="{70 + k * 22}" width="{244 - (k % 3) * 30}" height="8" fill="#d9d4c7"/>' for k in range(6)) + '</g>',
           # 湯呑み
           '<path d="M1380,520 L1440,520 L1432,590 L1388,590 Z" fill="#7aa38a"/><ellipse cx="1410" cy="520" rx="30" ry="8" fill="#5e8a70"/>',
           # 理事長（後ろ姿）と椅子
           '<rect x="820" y="760" width="280" height="40" rx="8" fill="#8a6a4a"/><rect x="840" y="800" width="20" height="230" fill="#7a5a3a"/><rect x="1060" y="800" width="20" height="230" fill="#7a5a3a"/>',
           '<path d="M800,780 Q800,600 960,600 Q1120,600 1120,780 Z" fill="#5b7fa6"/>',
           '<circle cx="960" cy="545" r="78" fill="#3b3a36"/>',
           '<path d="M1080,640 Q1150,560 1060,520" stroke="#5b7fa6" stroke-width="44" fill="none" stroke-linecap="round"/>',  # 頭に手をやる
           '<circle cx="1050" cy="515" r="26" fill="#f0c9a8"/>',
           # 困った気持ち（汗と「？」）
           '<text x="1120" y="420" font-size="90" font-weight="900" fill="#c8102e" opacity=".8">？</text>',
           '</svg>']
    return HEAD.format(css="") + "".join(svg) + "</body></html>"


def kairanban() -> str:
    """回覧板。住民への説明を回し、読んだ家が押印する（パターンC）。部屋番号は架空。"""
    rooms = ["101", "102", "103", "201", "202", "203", "301", "302"]
    seals = "".join(f'<div class="cell"><div class="rm">{r}</div>{"<div class=hk>済</div>" if k < 5 else ""}</div>' for k, r in enumerate(rooms))
    css = (".bg{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 40%,#e7dcc7,#cdbb9b)}"
           ".board{position:absolute;left:470px;top:70px;width:980px;height:820px;background:#4f7a5a;border-radius:18px;box-shadow:0 18px 40px rgba(0,0,0,.3)}"
           ".clip{position:absolute;left:390px;top:-18px;width:200px;height:70px;background:#9aa3ab;border-radius:10px;border:6px solid #7b848c}"
           ".hd{position:absolute;left:0;right:0;top:64px;text-align:center;color:#fff;font-size:46px;font-weight:900;letter-spacing:.5em}"
           ".doc{position:absolute;left:70px;top:150px;width:840px;height:430px;background:#fffdf7;padding:34px 40px}"
           ".doc b{display:block;font-size:34px;font-weight:900;color:#2b2a27}.doc span{display:block;font-size:22px;color:#52514e;margin:8px 0 18px}"
           ".doc .ln{height:11px;background:#e2ddd0;border-radius:3px;margin:16px 0}"
           ".seals{position:absolute;left:70px;top:610px;width:840px;display:grid;grid-template-columns:repeat(8,1fr);gap:8px}"
           ".cell{background:#fffdf7;height:150px;position:relative;text-align:center}.rm{font-size:20px;font-weight:700;color:#52514e;border-bottom:2px solid #e2ddd0;padding:6px 0}"
           ".hk{position:absolute;left:50%;top:70px;transform:translateX(-50%) rotate(-10deg);width:62px;height:62px;border:4px solid #c8102e;border-radius:50%;"
           "color:#c8102e;font-size:30px;font-weight:900;line-height:54px}"
           "")
    body = ('<div class="bg"></div><div class="board"><div class="clip"></div><div class="hd">回覧</div>'
            '<div class="doc"><b>管理規約の改定について</b><span>住民の皆さまへ　さくら台マンション管理組合 理事会（架空）</span>'
            + "".join(f'<div class="ln" style="width:{w}%"></div>' for w in (96, 90, 94, 70, 88, 92, 60)) + '</div>'
            f'<div class="seals">{seals}</div></div>')
    return HEAD.format(css=css) + body + "</body></html>"


FILES = {
    "05_danchi.html": landscape(),  # 0:00・2:50 の景色（撮影した動画に差し替える）
    "06_soukai.html": meeting(),  # 0:05 集会室での総会
    "07_law.html": law_paper(),  # 0:17 法律の条文（判子を重ねる）
    "07s_stamp_shikou.html": stamp("2026.4.1", "施行"),
    "07s_stamp_kaketsu.html": stamp("第25期総会", "可決"),
    "08_shuuzen.html": scaffold(),  # 0:31 大規模修繕の足場（素材集の写真か撮影に差し替える）
    "10_keijiban.html": keijiban(),  # パターンC 冒頭：掲示板のお知らせ
    "11_rijicho.html": rijicho(),  # パターンC：悩む理事長
    "12_kairanban.html": kairanban(),  # パターンC：回覧板
}
for name, html in FILES.items():
    (SRC / name).write_text(html, encoding="utf-8")
print("作成", ", ".join(FILES))
