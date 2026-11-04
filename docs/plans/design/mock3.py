"""デザインの見直し 第3案：第2案の中身のまま、見た目を「デザインの約束」で作り直したラフ案。

デザインの約束（docs/plans/デザイン見直し.md の第3案）：
  文字 … BIZ UDPゴシック（UD 書体）。大きさは 14/16/18/22/28/36、太さは 400 と 700 だけ。本文の行の高さ 1.8、見出し 1.4。見出しは palt、数字は tabular-nums
  色   … 地と文字の灰を3段。主の色は藍の1色。区分の色は彩度を落とす。朱は判子だけ
  余白 … 4 と 8 の倍数。箱で区切らず、余白と細い区切り線で区切る（箱の中に箱は作らない）
  丸み … 6px と 4px の2種類。影は使わない
  部品 … 絞り込みは下線のタブ。ラベルは文字と左の細い印。主のボタンは1画面に1つ、ほかは文字だけのボタン
  アイコン … 線のアイコン（Lucide の形を写した SVG。MIT）をページの中に直接書く
  ロゴ … 文字のロゴと、そろった3本の線の印（判子に見えないもの）
使い方: python3 docs/plans/design/mock3.py && node docs/plans/design/render3.js
"""

from pathlib import Path

OUT = Path(__file__).parent / "v3"
OUT.mkdir(exist_ok=True)
UD = "https://cdn.jsdelivr.net/npm/@fontsource/biz-udpgothic@5.0.12/files/biz-udpgothic-japanese-"

# 線のアイコン（Lucide の形。MIT License）
def icon(name: str, size=20, color="currentColor", sw=2) -> str:
    paths = {
        "check": '<path d="M20 6 9 17l-5-5"/>',
        "chev-down": '<path d="m6 9 6 6 6-6"/>',
        "chev-up": '<path d="m18 15-6-6-6 6"/>',
        "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
        "text-size": '<path d="M3 7V5h10v2"/><path d="M8 5v14"/><path d="M6 19h4"/><path d="M14 13v-1h7v1"/><path d="M17.5 12v7"/><path d="M16 19h3"/>',
        "file": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 13h6"/><path d="M10 17h6"/>',
        "printer": '<path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M6 14h12v8H6z"/>',
        "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
        "scale": '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
        "help": '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
        "list": '<path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/>',
    }[name]
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="{sw}" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="flex:none">{paths}</svg>')


LOGO = ('<svg width="30" height="30" viewBox="0 0 30 30" aria-hidden="true"><rect x="1" y="1" width="28" height="28" rx="6" fill="#24456b"/>'
        '<path d="M8 10h14M8 15h14M8 20h9" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/></svg>')

CSS = f"""@font-face{{font-family:U;font-weight:400;src:url({UD}400-normal.woff2)}}@font-face{{font-family:U;font-weight:700;src:url({UD}700-normal.woff2)}}
:root{{--bg:#f6f5f2;--surface:#ffffff;--ink:#1b1d20;--ink2:#474c53;--ink3:#61666d;--line:#e2dfd8;--line2:#cfcbc2;
--primary:#24456b;--primary-soft:#edf1f6;--must:#9a3324;--rec:#2b4f7a;--ref:#5d6167;--ok:#2d6a4f;--shu:#c8102e;
--s1:4px;--s2:8px;--s3:12px;--s4:16px;--s5:24px;--s6:32px;--s7:48px;--r1:6px;--r2:4px}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:var(--bg);color:var(--ink);font-family:U,sans-serif;font-size:18px;line-height:1.8;font-weight:400;-webkit-font-smoothing:antialiased}}
h1,h2,h3,.tt{{font-feature-settings:"palt";line-height:1.4;font-weight:700}}
.num{{font-variant-numeric:tabular-nums}}
.hdr{{display:flex;align-items:center;gap:var(--s3);height:64px;padding:0 var(--s6);background:var(--surface);border-bottom:1px solid var(--line)}}
.brand{{display:flex;align-items:center;gap:10px}}.brand b{{font-size:22px;letter-spacing:.08em;font-feature-settings:"palt"}}
.brand span{{font-size:14px;color:var(--ink3);border-left:1px solid var(--line2);padding-left:12px;margin-left:4px}}
.sp{{flex:1}}.tbtn{{display:inline-flex;align-items:center;gap:6px;min-height:44px;padding:0 10px;font-size:16px;color:var(--ink2)}}
.main{{max-width:960px;margin:0 auto;padding:var(--s6) var(--s5) 128px}}
.flow{{display:grid;grid-template-columns:repeat(6,1fr);margin-bottom:var(--s6)}}
.flow .c{{position:relative;text-align:center;font-size:14px;color:var(--ink2)}}
.flow .c::before{{content:"";position:absolute;top:15px;left:0;right:0;height:2px;background:var(--line2)}}
.flow .c:first-child::before{{left:50%}}.flow .c:last-child::before{{right:50%}}
.flow .c.done::before{{background:var(--primary)}}.flow .c.now::before{{background:linear-gradient(90deg,var(--primary) 50%,var(--line2) 50%)}}
.flow .m{{position:relative;width:32px;height:32px;margin:0 auto 6px;border-radius:50%;background:var(--surface);border:2px solid var(--line2);display:flex;align-items:center;justify-content:center}}
.flow .done .m{{border-color:var(--primary);color:var(--primary)}}.flow .now .m{{background:var(--primary);border-color:var(--primary)}}
.flow .now{{color:var(--ink);font-weight:700}}
.hanko{{border:2px solid var(--shu)!important;color:var(--shu)!important;font-weight:700;font-size:13px;transform:rotate(-10deg)}}
.eyebrow{{font-size:14px;color:var(--ink3);letter-spacing:.06em;margin-bottom:var(--s1)}}
h1{{font-size:28px;margin-bottom:var(--s4)}}
.lead{{font-size:18px;color:var(--ink2);max-width:40em;margin-bottom:var(--s5)}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid var(--line2);border-bottom:1px solid var(--line);margin-bottom:var(--s5)}}
.stats>div{{padding:var(--s4) 0}}.stats>div+div{{border-left:1px solid var(--line);padding-left:var(--s5)}}
.stats .k{{font-size:14px;color:var(--ink3)}}.stats .v{{font-size:36px;font-weight:700;line-height:1.3}}.stats .v small{{font-size:16px;font-weight:400;color:var(--ink2);margin-left:4px}}
.meter{{height:4px;background:var(--line);margin-top:var(--s2)}}.meter i{{display:block;height:100%;background:var(--primary)}}
.tabs{{display:flex;gap:var(--s5);border-bottom:1px solid var(--line2);margin-bottom:var(--s2)}}
.tabs span{{padding:var(--s2) 0 10px;font-size:16px;color:var(--ink2);border-bottom:3px solid transparent;margin-bottom:-1px;min-height:44px;display:inline-flex;align-items:center;gap:6px}}
.tabs span.on{{color:var(--ink);font-weight:700;border-bottom-color:var(--primary)}}
.tabs .n{{font-size:14px;color:var(--ink3);font-style:normal}}
.bulk{{display:flex;align-items:center;gap:var(--s2);font-size:16px;color:var(--ink2);padding:var(--s2) 0 var(--s4)}}
.link{{color:var(--primary);font-weight:700;text-decoration:underline;text-underline-offset:4px;text-decoration-thickness:1px}}
.item{{border-bottom:1px solid var(--line);padding:var(--s4) 0}}
.item .h{{display:grid;grid-template-columns:72px 1fr auto 28px;gap:var(--s3);align-items:baseline}}
.cat{{font-size:14px;font-weight:700;padding-left:10px;border-left:3px solid currentColor;line-height:1.3}}
.cat.must{{color:var(--must)}}.cat.rec{{color:var(--rec)}}.cat.ref{{color:var(--ref)}}
.tt{{font-size:18px}}.sub{{display:block;font-size:16px;color:var(--ink2);font-weight:400;line-height:1.7;margin-top:2px}}
.st{{display:inline-flex;align-items:center;gap:6px;font-size:15px;color:var(--ink2);white-space:nowrap}}.st.ok{{color:var(--ok)}}
.chev{{color:var(--ink3);align-self:center}}
.item.open{{background:var(--surface);margin:0 calc(-1*var(--s5));padding:var(--s5);border:1px solid var(--line);border-radius:var(--r1)}}
.facts{{display:grid;grid-template-columns:120px 1fr;gap:var(--s2) var(--s4);margin:var(--s4) 0 var(--s4) 84px;font-size:16px}}
.facts dt{{color:var(--ink3)}}.facts dd{{color:var(--ink)}}.facts .law{{color:var(--primary);text-decoration:underline;text-underline-offset:3px}}
.seg{{display:grid;grid-template-columns:repeat(3,1fr);border:1px solid var(--line2);border-radius:var(--r1);overflow:hidden;margin-left:84px}}
.seg div{{min-height:56px;padding:var(--s2) var(--s4);font-size:17px;display:flex;align-items:center;gap:8px;background:var(--surface)}}
.seg div+div{{border-left:1px solid var(--line2)}}.seg .on{{background:var(--primary-soft);color:var(--primary);font-weight:700;box-shadow:inset 0 -3px 0 var(--primary)}}
.reason{{display:flex;gap:var(--s3);align-items:center;margin:var(--s3) 0 0 84px}}
.field{{flex:1;min-height:48px;border:1px solid var(--line2);border-radius:var(--r1);padding:10px 14px;color:var(--ink3);background:var(--surface);font-size:16px}}
.btn{{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;padding:0 var(--s5);border-radius:var(--r1);background:var(--primary);color:#fff;font-weight:700;font-size:17px;white-space:nowrap}}
.tbtn2{{display:inline-flex;align-items:center;min-height:44px;padding:0 var(--s2);color:var(--primary);font-weight:700;font-size:16px}}
.note{{margin:var(--s2) 0 0 84px;font-size:15px;color:var(--ink2)}}
.bar{{position:fixed;left:0;right:0;bottom:0;background:var(--surface);border-top:1px solid var(--line2)}}
.bar .in{{max-width:960px;margin:0 auto;padding:var(--s3) var(--s5);display:flex;align-items:center;gap:var(--s4)}}
.bar .t{{flex:1;font-size:16px;color:var(--ink2)}}.bar .t b{{color:var(--ink);font-size:18px}}
.sec{{border-top:1px solid var(--line2);padding:var(--s5) 0}}.sec h2{{font-size:22px;margin-bottom:var(--s3)}}
.check{{display:flex;gap:var(--s3);align-items:flex-start;padding:var(--s2) 0}}
.pill-ok{{color:var(--ok);font-weight:700}}
.acts{{display:flex;gap:var(--s5);margin-top:var(--s3)}}
.agenda{{display:grid;grid-template-columns:1fr 120px;align-items:center;border-bottom:1px solid var(--line);padding:var(--s4) 0}}
.agenda .tt{{font-size:20px}}
.seal{{width:96px;height:96px;border:4px solid var(--shu);border-radius:50%;color:var(--shu);font-weight:700;font-size:28px;display:flex;align-items:center;justify-content:center;transform:rotate(-9deg);letter-spacing:.04em;justify-self:end}}
.doc{{display:flex;align-items:center;gap:var(--s4);background:var(--surface);border:1px solid var(--line);border-radius:var(--r1);padding:var(--s5);margin-top:var(--s5)}}
.foot{{text-align:center;color:var(--ink3);font-size:14px;margin-top:var(--s6)}}
.sp .item .h{{grid-template-columns:1fr 28px;row-gap:4px}}.sp .item .h .cat{{grid-column:1;grid-row:1;justify-self:start}}.sp .item .h .chev{{grid-column:2;grid-row:1}}
.sp .item .h .tt{{grid-column:1/3;grid-row:2}}.sp .item .h .st{{grid-column:1/3;grid-row:3}}
.sp .seg div+div{{border-left:none;border-top:1px solid var(--line2)}}.sp .reason .field{{flex-basis:100%}}
"""


def page(body: str, width=1280) -> str:
    cls = ' class="sp"' if width < 500 else ""
    return f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>{CSS}</style></head><body{cls} style="width:{width}px">{body}</body></html>'


def header(sp=False) -> str:
    if sp:
        return (f'<div class="hdr" style="padding:0 16px;height:56px"><div class="brand">{LOGO}<b style="font-size:19px">ととのう規約</b></div><span class="sp"></span>'
                f'<span class="tbtn">{icon("text-size", 22)}</span></div>')
    return (f'<div class="hdr"><div class="brand">{LOGO}<b>ととのう規約</b><span>管理規約を、改正法に合わせる</span></div><span class="sp"></span>'
            f'<span class="tbtn">{icon("text-size")}文字の大きさ</span><span class="tbtn">{icon("help")}使い方</span><span class="tbtn">{icon("list")}これまでの見直し</span></div>')


STEPS = [("読み込み", "ai"), ("指摘の判断", "human"), ("改定案", "ai"), ("理事会で検討", "human"), ("住民への説明", "ai"), ("総会のあと", "human")]


def flow(current: int, sp=False) -> str:
    """進み具合（回覧の押印欄を、細い帯と小さな印で）。人が判断した段は「済」の判子、AI が作る段は線のチェック。"""
    cells = []
    for k, (s, who) in enumerate(STEPS):
        if k < current:
            cls = "done"
            mark = '<div class="m hanko">済</div>' if who == "human" else f'<div class="m">{icon("check", 16, "currentColor", 2.5)}</div>'
        elif k == current:
            cls, mark = "now", '<div class="m"><span style="width:10px;height:10px;border-radius:50%;background:#fff"></span></div>'
        else:
            cls, mark = "", '<div class="m"></div>'
        label = "" if sp else f"{k + 1}. {s}"
        cells.append(f'<div class="c {cls}">{mark}{label}</div>')
    tail = (f'<div style="font-size:14px;color:var(--ink2);margin:-24px 0 24px">いま：<b style="color:var(--ink)">{current + 1}. {STEPS[current][0]}</b>（全6ステップ）</div>' if sp else "")
    return f'<div class="flow">{"".join(cells)}</div>{tail}'


def items(sp=False) -> str:
    chev_d, chev_u = icon("chev-down", 20), icon("chev-up", 20)
    ok = f'<span class="st ok">{icon("check", 18)}改定案に入っています</span>'
    open_item = (
        f'<div class="item open"><div class="h"><span class="cat rec">推奨</span>'
        f'<span class="tt">所在が分からない人を、決議の数から外す手続き<span class="sub">裁判所の決定で、連絡がつかない区分所有者を、総会の決議の母数から外せる手続きを定めます</span></span>'
        f'<span class="st">あとで決める</span><span class="chev">{chev_u}</span></div>'
        f'<dl class="facts"><dt>今の規定</dt><dd>定めがありません</dd><dt>根拠</dt><dd><span class="law">区分所有法 第38条の2</span>（所在等不明区分所有者の除外）<br><span class="law">標準管理規約 第67条の3</span></dd></dl>'
        f'<div class="seg"><div class="on">{icon("check", 18)}改定案に入れる</div><div>今回は見送る</div><div>あとで決める</div></div>'
        f'<div class="reason"><span class="field">理由（任意）　例：高齢の所有者が増えているため</span><span class="btn">確定する</span><span class="tbtn2">取り消す</span></div>'
        f'<div class="note">「あとで決める」から「改定案に入れる」に変えます。「確定する」で保存し、履歴に残ります。</div></div>')
    rows = [
        f'<div class="item"><div class="h"><span class="cat must">必須</span><span class="tt">特別決議を、出席者の多数決に<span class="sub">全員の4分の3 から、出席者の4分の3 へ</span></span>{ok}<span class="chev">{chev_d}</span></div></div>',
        open_item,
        f'<div class="item"><div class="h"><span class="cat rec">推奨</span><span class="tt">国外に住む区分所有者の、国内管理人の届出<span class="sub">国外に住む人が管理人を選んだときの届出を定めます</span></span><span class="st ok">{icon("check", 18)}改定案に入れる</span><span class="chev">{chev_d}</span></div></div>',
        f'<div class="item"><div class="h"><span class="cat ref">参考</span><span class="tt">古い用語「マンション敷地売却」の言い換え<span class="sub">改正法の用語「建物敷地売却」に合わせます</span></span><span class="st">あとで決める</span><span class="chev">{chev_d}</span></div></div>',
    ]
    html = "".join(rows)
    if sp:
        html = (html.replace('grid-template-columns:72px 1fr auto 28px', '')
                .replace('class="facts"', 'class="facts" style="margin-left:0;grid-template-columns:1fr"')
                .replace('class="seg"', 'class="seg" style="margin-left:0;grid-template-columns:1fr"')
                .replace('class="reason"', 'class="reason" style="margin-left:0;flex-wrap:wrap"')
                .replace('class="note"', 'class="note" style="margin-left:0"')
                .replace('class="item open"', 'class="item open" style="margin:0 -16px;padding:16px"'))
    return html


def decide(sp=False) -> str:
    stats = ('<div class="stats"><div><div class="k">改定案に入っている必須</div><div class="v num">7<small>件</small></div></div>'
             '<div><div class="k">このステップで決めること</div><div class="v num">17<small>件（推奨15・参考2）</small></div></div>'
             '<div><div class="k">判断済み</div><div class="v num">5<small>／ 17</small></div><div class="meter"><i style="width:29%"></i></div></div></div>')
    tabs = ('<div class="tabs"><span class="on">決めること <i class="n num">17</i></span><span>必須 <i class="n num">7</i></span><span>推奨 <i class="n num">15</i></span>'
            '<span>参考 <i class="n num">2</i></span><span>あとで決める <i class="n num">12</i></span></div>'
            '<div class="bulk">委員会でまとめて決めたときは、<span class="link">推奨の15件を、まとめて「改定案に入れる」</span>こともできます。</div>')
    bar = (f'<div class="bar"><div class="in"><div class="t"><b class="num">判断済み 5 ／ 17</b>　「あとで決める」のままでも先へ進めます</div>'
           f'<span class="btn">改定案を作る{icon("arrow-right", 20)}</span></div></div>')
    if sp:
        sp_stats = ('<div class="stats" style="grid-template-columns:1fr 1fr"><div><div class="k">決めること</div><div class="v num">17<small>件</small></div></div>'
                    '<div style="padding-left:16px"><div class="k">判断済み</div><div class="v num">5<small>／17</small></div></div></div>')
        body = (header(True) + '<div class="main" style="padding:24px 16px 120px">' + flow(1, True)
                + '<div class="eyebrow">ステップ 2 ／ 6</div><h1 style="font-size:24px">指摘を判断する</h1>'
                + '<p class="lead" style="font-size:17px">法律で必要な7件は、もう改定案に入っています。残りの17件を決めてください。</p>'
                + sp_stats + '<div class="tabs" style="gap:16px"><span class="on">決めること <i class="n num">17</i></span><span>必須 <i class="n num">7</i></span><span>推奨 <i class="n num">15</i></span></div>'
                + items(True) + '</div>'
                + f'<div class="bar"><div class="in" style="padding:12px 16px"><span class="btn" style="flex:1">改定案を作る{icon("arrow-right", 20)}</span></div></div>')
        return page(body, 390)
    body = (header() + '<div class="main">' + flow(1) + '<div class="eyebrow">ステップ 2 ／ 6</div><h1>指摘を判断する</h1>'
            '<p class="lead">法律で必要な7件は、もう改定案に入っています。このステップでは、残りの17件を、改定案に入れるかどうか決めてください。</p>'
            + stats + tabs + items() + '</div>' + bar)
    return page(body)


def draft() -> str:
    body = (header() + '<div class="main">' + flow(2) + '<div class="eyebrow">ステップ 3 ／ 6</div><h1>改定案を確かめる</h1>'
            '<p class="lead">改定案ができました。規約の改定は総会の特別決議、細則の改定は普通決議です。</p>'
            '<div class="stats"><div><div class="k">改定する条</div><div class="v num">20<small>条</small></div></div>'
            '<div><div class="k">規約 ／ 細則</div><div class="v num">18<small>条 ／ </small>2<small>条</small></div></div>'
            '<div><div class="k">作成にかかった時間</div><div class="v num">8<small>分</small></div></div></div>'
            '<div class="sec"><h2>確かめた結果</h2>'
            f'<div class="check">{icon("check", 22, "var(--ok)", 2.5)}<div>プログラムの確認（条番号・参照・数値など5項目）　<span class="pill-ok">問題なし</span></div></div>'
            f'<div class="check">{icon("check", 22, "var(--ok)", 2.5)}<div>別の AI の確認（11項目）　<span class="pill-ok">合格</span>（1回目で合格）　<span class="link">確認した項目を見る</span></div></div></div>'
            '<div class="sec"><h2>理事会の前に、人が確かめること</h2>'
            '<div class="check"><span class="num" style="color:var(--ink3)">1</span><div>新旧対照表で、直した文が委員会の意図どおりかを確かめる</div></div>'
            '<div class="check"><span class="num" style="color:var(--ink3)">2</span><div>組合が選ぶ点（〔選択〕）が<b>4か所</b>あります。次の「理事会で検討」で、どちらの案にするか選びます</div></div>'
            f'<div class="acts"><span class="tbtn2">{icon("file", 20)}　新旧対照表を開く</span><span class="tbtn2">{icon("printer", 20)}　印刷する</span><span class="tbtn2">指摘の判断に戻る</span></div></div>'
            '</div>'
            f'<div class="bar"><div class="in"><div class="t"><b>次は、理事会での検討です</b>　印刷用の検討資料を作り、議題ごとに判断を記録します</div><span class="btn">理事会の検討資料を作る{icon("arrow-right", 20)}</span></div></div>')
    return page(body)


def meeting() -> str:
    body = (header() + '<div class="main">' + flow(5) + '<div class="eyebrow">ステップ 6 ／ 6</div><h1>総会の結果と、最新の規約</h1>'
            '<p class="lead">総会の結果を記録すると、可決した改定を反映した最新の規約を作ります。ここは AI を使わず、プログラムで組み立てます。</p>'
            '<div style="border-top:1px solid var(--line2)">'
            '<div class="agenda"><div><span class="eyebrow">第1号議案　総会の特別決議</span><div class="tt">管理規約の改定（18条）</div></div><div class="seal">可決</div></div>'
            '<div class="agenda"><div><span class="eyebrow">第2号議案　総会の普通決議</span><div class="tt">総会運営細則の改定（2条）</div></div><div class="seal" style="transform:rotate(7deg)">可決</div></div></div>'
            f'<div class="doc">{icon("file", 32, "var(--primary)", 1.6)}<div style="flex:1"><div class="tt" style="font-size:20px">さくら台マンション管理規約（架空）　最新版</div>'
            '<div style="font-size:15px;color:var(--ink2)">令和8年5月24日 第25期定期総会で改正（附則つき）</div></div>'
            f'<span class="btn">{icon("download", 20)}Word でダウンロード</span></div>'
            '<div class="foot">出力は「総会提案の下書き」であり、法的助言ではありません。</div></div>')
    return page(body)


for name, html in {"v3_decide": decide(), "v3_decide_sp": decide(True), "v3_draft": draft(), "v3_meeting": meeting()}.items():
    (OUT / f"{name}.html").write_text(html, encoding="utf-8")
print("作成：v3_decide, v3_decide_sp, v3_draft, v3_meeting")
