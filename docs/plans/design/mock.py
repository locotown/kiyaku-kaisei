"""デザインの見直しのラフ案（3方向 × 同じ画面）を、静的な HTML として作る。見た目だけの粗い作り。

使い方: python3 docs/plans/design/mock.py && node docs/plans/design/render.js
中身は架空のサンプル（さくら台マンション管理組合）。実在のマンション・人物は出さない。
"""

from pathlib import Path

OUT = Path(__file__).parent
FONT = "https://cdn.jsdelivr.net/npm/@fontsource"
FACES = (f"@font-face{{font-family:N;font-weight:400;src:url({FONT}/noto-sans-jp@5.0.19/files/noto-sans-jp-japanese-400-normal.woff2)}}"
         f"@font-face{{font-family:N;font-weight:700;src:url({FONT}/noto-sans-jp@5.0.19/files/noto-sans-jp-japanese-700-normal.woff2)}}"
         f"@font-face{{font-family:N;font-weight:900;src:url({FONT}/noto-sans-jp@5.0.19/files/noto-sans-jp-japanese-900-normal.woff2)}}"
         f"@font-face{{font-family:S;font-weight:700;src:url({FONT}/noto-serif-jp@5.0.12/files/noto-serif-jp-japanese-700-normal.woff2)}}")

STEPS = ["読み込み", "指摘の判断", "改定案", "理事会での検討", "住民向けの説明", "総会後の最新規約"]
WORKS = [("2026年度 規約見直し（委員会案）", "さくら台マンション管理組合（架空）", "11月3日 21:40", "改定案あり（理事会での検討へ）", 3),
         ("サンプル：Word の規約集", "—", "11月2日 18:05", "点検済み（指摘の判断へ）", 1)]
F = {
    "title": "特別決議を出席者の多数決に",
    "target": "規約 第49条（総会の会議及び議事）",
    "issue": "規約の変更などの重要事項を「組合員総数の4分の3以上及び議決権総数の4分の3以上」で決めることになっており、欠席者も含めた全員が母数になっています。改正法では、総会に出席した人の各4分の3以上で決めます。",
    "now": "次の各号に掲げる事項に関する総会の議事は、前項にかかわらず、組合員総数の4分の3以上及び議決権総数の4分の3以上で決する。",
    "dir": "特別決議の要件を「出席組合員及びその議決権の各4分の3以上」に改める（標準管理規約 第47条第3項にならう）。",
    "basis": [("区分所有法", "第31条第1項", "規約の設定、変更及び廃止"), ("区分所有法", "第17条第1項", "共用部分の変更"), ("標準管理規約", "第47条第3項", "総会の会議及び議事")],
}
NEXT = "推奨・参考の指摘 15件の判断が残っています。判断を終えたら「改定案を作る」へ進みます。"
DISC = "出力は「総会提案の下書き」であり、法的助言ではありません。"

# 方向ごとの色・字体（CSS の変数）と、日本の要素の使い方
THEMES = {
    "A": {"name": "規約集", "vars": "--bg:#f6f1e7;--paper:#fffdf8;--ink:#1f1d1a;--ink2:#55504a;--line:#d9cfbd;--accent:#b3261e;--accent2:#1f3a5f;--soft:#f1e9da;--must:#b3261e;--rec:#1f3a5f;--ref:#6b6459",
          "head": "S", "radius": "4px"},
    "B": {"name": "掲示板・回覧板", "vars": "--bg:#e9dfcd;--paper:#ffffff;--ink:#1f1d1a;--ink2:#4f4a44;--line:#d8cbb4;--accent:#2f6b4f;--accent2:#c8102e;--soft:#f7f1e4;--must:#c8102e;--rec:#2a6cb8;--ref:#7a7368",
          "head": "N", "radius": "6px"},
    "C": {"name": "すっきり手順", "vars": "--bg:#f5f7fa;--paper:#ffffff;--ink:#0b0b0b;--ink2:#3d4450;--line:#d5dbe3;--accent:#1d5fbf;--accent2:#c8102e;--soft:#eef3fa;--must:#c0271c;--rec:#1d5fbf;--ref:#5b636e",
          "head": "N", "radius": "12px"},
}

BASE = """*{box-sizing:border-box;margin:0}html,body{background:var(--bg);color:var(--ink);font-family:N,sans-serif;font-size:17px;line-height:1.75}
.hdr{display:flex;align-items:center;gap:14px;padding:12px 28px;background:var(--paper);border-bottom:1px solid var(--line)}
.logo{font-family:H,N;font-weight:900;font-size:26px;letter-spacing:.06em}.tag{font-weight:700;color:var(--ink2);font-size:15px}
.wrap{max-width:1180px;margin:0 auto;padding:22px 28px}
h2{font-family:H,N;font-weight:700;font-size:24px;margin-bottom:10px}
.btn{display:inline-block;background:var(--accent);color:#fff;font-weight:700;border-radius:var(--r);padding:12px 26px;font-size:18px}
.btn.ghost{background:transparent;color:var(--accent);border:2px solid var(--accent)}
.muted{color:var(--ink2);font-size:15px}.disc{color:var(--ink2);font-size:13px;text-align:center;margin-top:18px}
.badge{display:inline-block;color:#fff;font-weight:700;font-size:14px;padding:2px 10px;border-radius:4px}
"""


def seal(text: str, size=64, color="var(--accent2)", rot=-8) -> str:
    return (f'<span style="display:inline-flex;align-items:center;justify-content:center;width:{size}px;height:{size}px;border:{max(3, size // 14)}px solid {color};'
            f'border-radius:50%;color:{color};font-weight:900;font-size:{size * 0.42:.0f}px;transform:rotate({rot}deg);font-family:N;line-height:1">{text}</span>')


def page(theme: str, body: str, extra_css: str = "", width=1280) -> str:
    t = THEMES[theme]
    head = "S" if t["head"] == "S" else "N"
    return (f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>{FACES}@font-face{{font-family:H;src:local("x")}}'
            f':root{{{t["vars"]};--r:{t["radius"]}}}{BASE}' + (f".logo,h2,h3,.serif{{font-family:{head},N}}" if head == "S" else "")
            + extra_css + f'</style></head><body style="width:{width}px">{body}</body></html>')


def header(theme: str) -> str:
    mark = {"A": seal("整", 40, "var(--accent)", 0), "B": seal("整", 40, "var(--accent2)", -10),
            "C": '<span style="display:inline-block;width:34px;height:34px;border-radius:9px;background:var(--accent)"></span>'}[theme]
    return f'<div class="hdr">{mark}<span class="logo">ととのう規約</span><span class="tag">管理規約を、改正法に合わせる</span></div>'


# ---------- ① トップ ----------
def index(theme: str) -> str:
    works = "".join(
        f'<div class="work"><div><b>{n}</b><div class="muted">{o}　／　最後の更新 {d}</div></div><div class="wstate">{s}</div>'
        f'<div class="wsteps">{"".join(f"<i class={chr(39)}on{chr(39)}></i>" if k < st else "<i></i>" for k in range(6))}</div>'
        f'<a class="btn ghost small">開く</a><span class="del">削除</span></div>' for n, o, d, s, st in WORKS)
    form = ('<div class="new"><h2>新しく見直しを始める</h2><div class="drop"><b>規約のファイルをここに置く</b><span class="muted">Word・文字を選べる PDF・テキスト</span></div>'
            '<div class="q3"><label>マンション名（任意）<span class="in">例：さくら台マンション管理組合</span></label>'
            '<label>メールやWebの利用<span class="in">未定（理事会で選ぶ）▾</span></label><label>戸数（任意）<span class="in">例：48</span></label></div>'
            '<a class="btn">点検を始める</a><span class="muted">　点検は3〜5分、AI の費用は約$1です</span></div>')
    samples = ('<div class="samples"><b>サンプルで試す</b>' + "".join(f'<span class="smp">{x}</span>' for x in ("改正前の標準管理規約", "細則を含む規約集（架空）", "古い規約（架空）", "Word の規約集（架空）")) + '</div>')
    css = {"A": ".hero{border-bottom:3px double var(--line);padding-bottom:14px;margin-bottom:18px}.work,.new,.samples{background:var(--paper);border:1px solid var(--line);border-left:5px solid var(--accent2)}",
           "B": ".hero{margin-bottom:16px}.work,.new,.samples{background:var(--paper);border:none;box-shadow:0 6px 16px rgba(60,40,10,.18);position:relative}.work::before,.new::before{content:'';position:absolute;top:-7px;left:50%;width:14px;height:14px;border-radius:50%;background:var(--accent2)}",
           "C": ".hero{margin-bottom:18px}.work,.new,.samples{background:var(--paper);border:1px solid var(--line);box-shadow:0 2px 6px rgba(0,0,0,.05)}"}[theme]
    css += (".work,.new,.samples{border-radius:var(--r);padding:16px 20px;margin-bottom:12px}.work{display:grid;grid-template-columns:1fr 260px 140px 90px 50px;gap:14px;align-items:center}"
            ".wstate{font-weight:700;color:var(--accent)}.wsteps i{display:inline-block;width:18px;height:8px;margin-right:3px;border-radius:2px;background:var(--line)}.wsteps i.on{background:var(--accent)}"
            ".btn.small{padding:6px 14px;font-size:15px}.del{color:var(--ink2);font-size:14px}.drop{border:2px dashed var(--accent);border-radius:var(--r);padding:22px;text-align:center;margin:8px 0 12px;background:var(--soft)}"
            ".drop b{display:block;font-size:20px}.q3{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:14px}.q3 label{font-weight:700;font-size:15px}"
            ".in{display:block;border:1px solid var(--line);border-radius:6px;padding:8px 10px;font-weight:400;color:var(--ink2);background:#fff;margin-top:4px}"
            ".samples{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.smp{border:1px solid var(--line);border-radius:999px;padding:4px 14px;font-size:15px;background:var(--soft)}")
    lead = {"A": "法律が変わった今、あなたの管理規約を、根拠の条文とともに見直します。",
            "B": "理事になったあなたへ。規約の見直しを、総会の可決まで、いっしょに進めます。",
            "C": "規約を読み込むだけ。直す箇所・改定案・住民への説明の下書きまで、順番に進めます。"}[theme]
    body = (header(theme) + f'<div class="wrap"><div class="hero"><h2 style="font-size:30px">{lead}</h2></div>'
            f'<h2>これまでの見直し</h2>{works}{form}{samples}<div class="disc">{DISC}</div></div>')
    return page(theme, body, css)


# ---------- ② 指摘カード（作業画面：指摘の判断の段階） ----------
def stepper(theme: str, current=1, vertical=True) -> str:
    items = []
    for k, s in enumerate(STEPS):
        state = "done" if k < current else ("now" if k == current else "todo")
        if theme == "A":
            label = f'<span class="no">第{"一二三四五六"[k]}</span>{s}'
        elif theme == "B":
            label = f'<span class="box">{seal("済", 30, "var(--accent2)", -12) if state == "done" else ""}</span>{s}'
        else:
            label = f'<span class="dot">{"✓" if state == "done" else k + 1}</span>{s}'
        items.append(f'<li class="{state}">{label}</li>')
    return f'<ol class="steps {"v" if vertical else "h"}">{"".join(items)}</ol>'


def card_html(theme: str, narrow=False) -> str:
    basis = "".join(f'<li><span class="src">{a}</span> {b} <span class="muted">（{c}）</span></li>' for a, b, c in F["basis"])
    pin = '<i class="pin"></i>' if theme == "B" else ""
    tape = '<span class="tape">必須</span>' if theme == "B" else '<span class="badge" style="background:var(--must)">必須</span>'
    return (f'<div class="card">{pin}<div class="ch">{tape}<h3>{F["title"]}</h3></div>'
            f'<div class="tg">対象：<b>{F["target"]}</b>　<span class="res">規約の変更 → 総会の特別決議</span></div>'
            f'<div class="sec"><div class="lb">何が問題か</div><p>{F["issue"]}</p></div>'
            f'<div class="sec"><div class="lb">今の規定</div><p class="quote">{F["now"]}</p></div>'
            f'<div class="sec"><div class="lb">改定の方向</div><p class="dir">{F["dir"]}</p></div>'
            f'<div class="sec"><div class="lb">根拠</div><ul class="basis">{basis}</ul></div>'
            f'<div class="sec"><div class="lb">委員会の判断</div><p class="fixed">✓ 改定案に入れます<span class="muted">（法律に合わせるため必ず入れます）</span></p></div></div>')


CARD_CSS = """.card{background:var(--paper);border-radius:var(--r);padding:18px 22px;position:relative}
.ch{display:flex;align-items:center;gap:12px;margin-bottom:6px}.ch h3{font-size:22px;font-weight:700}
.tg{font-size:15px;margin-bottom:8px}.res{font-size:13px;border:1px solid var(--rec);color:var(--rec);border-radius:4px;padding:1px 8px}
.sec{display:grid;grid-template-columns:120px 1fr;gap:12px;padding:8px 0;border-top:1px solid var(--line)}.lb{font-weight:700;color:var(--ink2);font-size:15px}
.quote{background:var(--soft);padding:6px 12px;border-radius:6px;font-size:15px}.dir{border-left:4px solid var(--rec);padding-left:12px}
.basis{list-style:none;padding:0}.src{display:inline-block;background:var(--ink);color:#fff;font-size:12px;font-weight:700;padding:1px 6px;border-radius:3px}
.fixed{color:#1e6b3a;font-weight:700}
.next{background:var(--paper);border-radius:var(--r);padding:12px 18px;margin-bottom:12px;font-size:16px}.next b{color:var(--accent)}
.filters span{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:3px 14px;margin-right:6px;font-size:15px;background:var(--paper)}.filters span.on{background:var(--ink);color:#fff}
.steps{list-style:none;padding:0}.steps li{font-size:16px;font-weight:700;color:var(--ink2)}.steps li.now{color:var(--ink)}.steps li.todo{opacity:.55}
"""


def card(theme: str) -> str:
    css = CARD_CSS + {
        "A": (".layout{display:grid;grid-template-columns:230px 1fr;gap:22px}.steps.v{background:var(--paper);border:1px solid var(--line);padding:12px 16px}"
              ".steps.v li{padding:7px 0;border-bottom:1px dotted var(--line)}.steps .no{display:inline-block;width:46px;color:var(--accent2);font-family:S,N}.steps li.now{color:var(--accent)}"
              ".card{border:1px solid var(--line);border-top:4px solid var(--must)}.next{border:1px solid var(--line);border-left:5px solid var(--accent)}"),
        "B": (".layout{display:grid;grid-template-columns:230px 1fr;gap:22px}.steps.v{background:#3f6b4e;border-radius:10px;padding:14px;color:#fff}"
              ".steps.v::before{content:'回覧';display:block;text-align:center;color:#fff;font-weight:900;letter-spacing:.4em;margin-bottom:8px}"
              ".steps.v li{display:flex;align-items:center;gap:10px;background:#fffdf7;border-radius:4px;margin-bottom:6px;padding:4px 8px}"
              ".steps .box{display:inline-flex;width:34px;height:34px;border:1px solid var(--line);align-items:center;justify-content:center}"
              ".card{box-shadow:0 8px 20px rgba(60,40,10,.22);transform:rotate(-.4deg)}.pin{position:absolute;top:-8px;left:50%;width:18px;height:18px;border-radius:50%;background:var(--must);box-shadow:0 2px 3px rgba(0,0,0,.3)}"
              ".tape{background:var(--must);color:#fff;font-weight:900;padding:3px 14px;transform:rotate(-3deg);display:inline-block}.next{box-shadow:0 4px 10px rgba(60,40,10,.15)}"),
        "C": (".layout{display:block}.steps.h{display:flex;gap:6px;margin-bottom:14px}.steps.h li{flex:1;text-align:center;font-size:14px;padding:8px 4px;border-radius:10px;background:var(--paper);border:1px solid var(--line)}"
              ".steps.h li.now{background:var(--accent);color:#fff;border-color:var(--accent)}.steps.h li.done{color:#1e6b3a}"
              ".steps .dot{display:block;font-size:18px}.card{border:1px solid var(--line);box-shadow:0 2px 8px rgba(0,0,0,.05);font-size:18px}.card p{font-size:18px}"
              ".next{border:2px solid var(--accent);font-size:18px}.prog{font-weight:900;color:var(--accent);font-size:15px;margin-bottom:6px}"),
    }[theme]
    st = stepper(theme, 1, vertical=theme != "C")
    main = (f'<div class="next"><b>次にすること：</b>{NEXT}</div>'
            '<div class="filters" style="margin-bottom:12px"><span class="on">すべて 24</span><span>必須 7</span><span>推奨 15</span><span>参考 2</span><span>保留中 12</span></div>'
            + card_html(theme))
    if theme == "C":
        body = header(theme) + f'<div class="wrap"><div class="prog">ステップ 2 / 6　指摘の判断</div>{st}{main}</div>'
    else:
        body = header(theme) + f'<div class="wrap"><div class="layout">{st}<div>{main}</div></div></div>'
    return page(theme, body, css)


def card_sp(theme: str) -> str:
    css = CARD_CSS + (".wrap{padding:12px}.sec{grid-template-columns:1fr;gap:2px}.ch h3{font-size:20px}.hdr{padding:10px 14px}.logo{font-size:21px}.tag{display:none}"
                      ".mini{font-weight:900;color:var(--accent);margin-bottom:8px}") + {
        "A": ".card{border:1px solid var(--line);border-top:4px solid var(--must)}.next{border-left:5px solid var(--accent)}",
        "B": ".card{box-shadow:0 8px 20px rgba(60,40,10,.22)}.pin{position:absolute;top:-8px;left:50%;width:16px;height:16px;border-radius:50%;background:var(--must)}.tape{background:var(--must);color:#fff;font-weight:900;padding:2px 12px;transform:rotate(-3deg);display:inline-block;white-space:nowrap}",
        "C": ".card{border:1px solid var(--line);font-size:18px}.next{border:2px solid var(--accent)}",
    }[theme]
    mini = {"A": "第二　指摘の判断（6段のうち2）", "B": "回覧：2 / 6　指摘の判断", "C": "ステップ 2 / 6　指摘の判断"}[theme]
    body = header(theme) + f'<div class="wrap"><div class="mini">{mini}</div><div class="next"><b>次にすること：</b>推奨・参考の判断が15件残っています。</div>{card_html(theme, True)}</div>'
    return page(theme, body, css, width=390)


# ---------- ③ 総会の結果と最新の規約 ----------
def meeting(theme: str) -> str:
    stamp = seal("可決", 92, "#c8102e", -10)
    rows = (f'<div class="agenda"><div><b>第1号議案　管理規約の改定</b><div class="muted">改定 20条　／　総会の特別決議</div></div><div class="res2">{stamp}</div></div>'
            f'<div class="agenda"><div><b>第2号議案　総会運営細則の改定</b><div class="muted">改定 2条　／　総会の普通決議</div></div><div class="res2">{seal("可決", 92, "#c8102e", 6)}</div></div>')
    final = ('<div class="final"><div><b>さくら台マンション管理規約（架空）　最新版</b><div class="muted">令和8年5月24日 第25期定期総会で改正（附則つき）</div></div>'
             '<a class="btn">Word でダウンロード</a></div>')
    css = (".agenda{display:flex;justify-content:space-between;align-items:center;background:var(--paper);border-radius:var(--r);padding:14px 20px;margin-bottom:10px}"
           ".final{display:flex;justify-content:space-between;align-items:center;background:var(--soft);border-radius:var(--r);padding:16px 20px;margin-top:14px}"
           ".layout{display:grid;grid-template-columns:230px 1fr;gap:22px}.steps{list-style:none;padding:0}.steps li{font-weight:700;color:var(--ink2)}.steps li.todo{opacity:.55}") + {
        "A": ".agenda,.final{border:1px solid var(--line)}.steps.v{background:var(--paper);border:1px solid var(--line);padding:12px 16px}.steps.v li{padding:7px 0;border-bottom:1px dotted var(--line)}.steps .no{display:inline-block;width:46px;color:var(--accent2);font-family:S,N}.steps li.now{color:var(--accent)}",
        "B": (".agenda,.final{box-shadow:0 6px 16px rgba(60,40,10,.18)}.steps.v{background:#3f6b4e;border-radius:10px;padding:14px}"
              ".steps.v::before{content:'回覧';display:block;text-align:center;color:#fff;font-weight:900;letter-spacing:.4em;margin-bottom:8px}"
              ".steps.v li{display:flex;align-items:center;gap:10px;background:#fffdf7;border-radius:4px;margin-bottom:6px;padding:4px 8px}.steps .box{display:inline-flex;width:34px;height:34px;border:1px solid var(--line);align-items:center;justify-content:center}"),
        "C": (".layout{display:block}.steps.h{display:flex;gap:6px;margin-bottom:14px}.steps.h li{flex:1;text-align:center;font-size:14px;padding:8px 4px;border-radius:10px;background:var(--paper);border:1px solid var(--line)}"
              ".steps.h li.now{background:var(--accent);color:#fff}.steps .dot{display:block;font-size:18px}.agenda,.final{border:1px solid var(--line)}.prog{font-weight:900;color:var(--accent);font-size:15px;margin-bottom:6px}"),
    }[theme]
    st = stepper(theme, 5, vertical=theme != "C")
    main = (f'<h2>第25期 定期総会の結果</h2><div class="muted" style="margin-bottom:10px">結果は理事会が記録しました。判子は、人が記録した結果にだけ押します。</div>{rows}{final}'
            f'<div class="disc">{DISC}</div>')
    body = header(theme) + (f'<div class="wrap"><div class="prog">ステップ 6 / 6　総会後の最新規約</div>{st}{main}</div>' if theme == "C"
                            else f'<div class="wrap"><div class="layout">{st}<div>{main}</div></div></div>')
    return page(theme, body, css)


for th in THEMES:
    for name, fn in (("index", index), ("card", card), ("meeting", meeting), ("card_sp", card_sp)):
        (OUT / f"{th}_{name}.html").write_text(fn(th), encoding="utf-8")
print("作成：", ", ".join(f"{t}_*" for t in THEMES))
