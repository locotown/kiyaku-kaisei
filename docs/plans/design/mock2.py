"""デザインの見直し 第2案（C を土台に B の要素を2か所）。想定ユーザー（理事・規約見直しの担当者）に合わせて作り直したラフ案。

画面の中の要素に data-n（説明の番号）を付けておき、annotate.js が画面の外に番号と説明を描く。
使い方: python3 docs/plans/design/mock2.py && node docs/plans/design/annotate.js
中身は架空のサンプル（さくら台マンション管理組合）。件数はデモ用の作業（指摘24件：必須7・推奨15・参考2）に合わせた。
"""

from pathlib import Path

OUT = Path(__file__).parent / "v2"
OUT.mkdir(exist_ok=True)
FONT = "https://cdn.jsdelivr.net/npm/@fontsource/noto-sans-jp@5.0.19/files/noto-sans-jp-japanese-"
CSS = f"""@font-face{{font-family:N;font-weight:400;src:url({FONT}400-normal.woff2)}}@font-face{{font-family:N;font-weight:700;src:url({FONT}700-normal.woff2)}}@font-face{{font-family:N;font-weight:900;src:url({FONT}900-normal.woff2)}}
:root{{--bg:#f4f6f9;--paper:#fff;--ink:#111418;--ink2:#3d4450;--line:#cfd6df;--accent:#1d5fbf;--soft:#eaf1fb;--must:#b42318;--rec:#1d5fbf;--ref:#4b5563;--ok:#16653a;--shu:#c8102e;--kai:#2f6b4f}}
*{{box-sizing:border-box;margin:0}}html,body{{background:var(--bg);color:var(--ink);font-family:N,sans-serif;font-size:18px;line-height:1.75}}
.hdr{{display:flex;align-items:center;gap:14px;padding:10px 24px;background:var(--paper);border-bottom:1px solid var(--line)}}
.logo{{font-weight:900;font-size:24px;letter-spacing:.06em}}.tagl{{font-weight:700;color:var(--ink2);font-size:15px}}.sp{{flex:1}}
.tool{{border:2px solid var(--line);border-radius:10px;padding:6px 14px;font-weight:700;font-size:16px;background:#fff;min-height:44px;display:inline-flex;align-items:center;gap:6px}}
.wrap{{max-width:1120px;margin:0 auto;padding:16px 24px 120px}}
.kairan{{display:grid;grid-template-columns:repeat(6,1fr);border:3px solid var(--kai);border-radius:12px;overflow:hidden;background:#fff;margin-bottom:14px}}
.kairan div{{border-right:1px solid #c9d8cf;padding:6px 6px 8px;text-align:center;font-weight:700;font-size:15px;color:var(--ink2);min-height:84px}}.kairan div:last-child{{border-right:none}}
.kairan .mk{{height:40px;display:flex;align-items:center;justify-content:center;font-size:24px;color:var(--ok)}}
.kairan .now{{background:var(--kai);color:#fff}}.kairan .now .mk{{color:#fff;font-size:15px}}
.seal{{display:inline-flex;align-items:center;justify-content:center;border:3px solid var(--shu);border-radius:50%;color:var(--shu);font-weight:900;transform:rotate(-10deg)}}
h1{{font-size:28px;font-weight:900;margin:4px 0 6px}}.step{{color:var(--accent);font-weight:900;font-size:16px}}
.sum{{background:var(--paper);border:2px solid var(--accent);border-radius:12px;padding:14px 18px;margin:8px 0 14px}}
.bar{{height:12px;background:#dfe6ef;border-radius:6px;overflow:hidden;margin-top:8px}}.bar i{{display:block;height:100%;background:var(--accent)}}
.chips span{{display:inline-flex;align-items:center;min-height:44px;border:2px solid var(--line);border-radius:999px;padding:0 16px;margin:0 6px 6px 0;font-weight:700;font-size:16px;background:#fff}}.chips span.on{{background:var(--ink);color:#fff;border-color:var(--ink)}}
.bulk{{font-size:16px;color:var(--ink2);margin:2px 0 12px}}.bulk b{{color:var(--ink)}}.bulk u{{color:var(--accent);font-weight:700}}
.row{{background:var(--paper);border:1px solid var(--line);border-left:8px solid var(--rec);border-radius:12px;padding:12px 16px;margin-bottom:10px}}
.row.must{{border-left-color:var(--must)}}.row.ref{{border-left-color:var(--ref)}}
.rh{{display:flex;align-items:center;gap:12px}}.lab{{font-weight:900;font-size:14px;padding:3px 10px;border-radius:6px;color:#fff;white-space:nowrap}}
.lab.must{{background:var(--must)}}.lab.rec{{background:var(--rec)}}.lab.ref{{background:var(--ref)}}
.tt{{font-weight:900;font-size:20px}}.one{{color:var(--ink2);font-size:17px}}.open{{color:var(--accent);font-weight:700;font-size:16px;white-space:nowrap}}
.state{{margin-left:auto;font-weight:900;font-size:16px;white-space:nowrap}}
.choice{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:12px 0 8px}}
.choice div{{border:2px solid var(--line);border-radius:12px;min-height:64px;padding:8px 12px;font-weight:900;font-size:18px;background:#fff}}.choice div small{{display:block;font-weight:400;font-size:14px;color:var(--ink2)}}
.choice .sel{{border-color:var(--ok);background:#ecf7f0;box-shadow:inset 0 0 0 2px var(--ok)}}
.reason{{display:flex;gap:10px;align-items:center}}.reason .in{{flex:1;border:2px solid var(--line);border-radius:10px;min-height:48px;padding:8px 12px;color:var(--ink2);background:#fff}}
.btn{{display:inline-flex;align-items:center;justify-content:center;min-height:52px;padding:0 22px;border-radius:12px;background:var(--accent);color:#fff;font-weight:900;font-size:18px}}
.btn.ghost{{background:#fff;color:var(--accent);border:2px solid var(--accent)}}
.saved{{color:var(--ok);font-weight:700;font-size:15px;margin-top:6px}}
.detail{{border-top:1px dashed var(--line);margin-top:10px;padding-top:8px;font-size:16px;color:var(--ink2)}}
.next{{position:fixed;left:0;right:0;bottom:0;background:#fff;border-top:2px solid var(--line);padding:12px 24px;display:flex;align-items:center;gap:16px;box-shadow:0 -6px 16px rgba(0,0,0,.06)}}
.next .t{{flex:1;font-size:16px;color:var(--ink2)}}.next .t b{{color:var(--ink);font-size:18px}}
.card{{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:16px 20px;margin-bottom:12px}}
.okline{{font-size:22px;font-weight:900;color:var(--ok)}}
.list li{{margin:4px 0 4px 1.2em}}
.agenda{{display:flex;align-items:center;justify-content:space-between;background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 20px;margin-bottom:10px}}
"""


def page(body: str, width=1280) -> str:
    return f'<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>{CSS}</style></head><body style="width:{width}px">{body}</body></html>'


def header(sp=False) -> str:
    seal = '<span class="seal" style="width:38px;height:38px;font-size:17px">整</span>'
    if sp:
        return f'<div class="hdr" style="padding:8px 12px">{seal}<span class="logo" style="font-size:20px">ととのう規約</span><span class="sp"></span><span class="tool" data-n="13">文字 大</span></div>'
    return (f'<div class="hdr">{seal}<span class="logo">ととのう規約</span><span class="tagl">管理規約を、改正法に合わせる</span><span class="sp"></span>'
            '<span class="tool" data-n="13">文字を大きく</span><span class="tool">使い方</span><span class="tool">これまでの見直し</span></div>')


def kairan(current: int, sp=False) -> str:
    """進み具合（回覧板の押印欄）。人が判断した段だけ「済」の判子、AI が作る段は ✓。"""
    steps = [("読み込み", "ai"), ("指摘の判断", "human"), ("改定案", "ai"), ("理事会で検討", "human"), ("住民への説明", "ai"), ("総会のあと", "human")]
    cells = []
    for k, (s, who) in enumerate(steps):
        if k < current:
            mk = '<span class="seal" style="width:36px;height:36px;font-size:15px">済</span>' if who == "human" else "✓"
            cls = ""
        elif k == current:
            mk, cls = "いまここ", "now"
        else:
            mk, cls = "", ""
        if sp:  # スマホの幅：番号と印だけ。今のステップ名は下に出す
            mk = "いま" if k == current else mk
            cells.append(f'<div class="{cls}" style="min-height:60px;padding:4px 2px"><div class="mk" style="height:30px;font-size:18px">{mk}</div>{k + 1}</div>')
        else:
            cells.append(f'<div class="{cls}"><div class="mk">{mk}</div>{k + 1}. {s}</div>')
    if sp:
        return (f'<div class="kairan" data-n="12" style="margin-bottom:4px">{"".join(cells)}</div>'
                f'<div style="font-size:15px;font-weight:700;color:var(--kai);margin-bottom:8px">いま：{current + 1}. {steps[current][0]}（全6ステップ）</div>')
    return f'<div class="kairan" data-n="12">{"".join(cells)}</div>'


ROWS_HTML = """
<div class="row must" data-n="4"><div class="rh"><span class="lab must">必須</span><span class="tt">特別決議を、出席者の多数決に</span>
  <span class="one">全員の4分の3 → 出席者の4分の3</span><span class="state" style="color:var(--ok)">✓ 改定案に入っています</span><span class="open">詳しく ▾</span></div></div>
<div class="row" data-n="1"><div class="rh"><span class="lab rec">推奨</span><span class="tt">所在が分からない人を、決議の数から外す手続き</span><span class="open">詳しく ▴</span></div>
  <div class="one" style="margin:4px 0 0 64px">何が変わるか：裁判所の決定で、連絡がつかない区分所有者を総会の決議の母数から外せる手続きを定めます</div>
  <div class="detail">今の規定：<i>（定めがありません）</i>　／　根拠：<b>区分所有法 第38条の2</b>（所在等不明区分所有者の除外）・<b>標準管理規約 第67条の3</b>　…（ここを開くと、条文の本文を読めます）</div>
  <div class="choice" data-n="5"><div class="sel">改定案に入れる<small>（採用）</small></div><div>今回は見送る<small>（不採用）</small></div><div>あとで決める<small>（保留）</small></div></div>
  <div class="reason" data-n="3"><span class="in">理由（任意）：例）高齢の所有者が増えているため</span><span class="btn">確定する</span><span class="btn ghost">取り消す</span></div>
  <div class="saved" data-n="2">いま「あとで決める」→「改定案に入れる」に変えようとしています。「確定する」で保存します（ページは動きません）</div></div>
<div class="row"><div class="rh"><span class="lab rec">推奨</span><span class="tt">国外に住む区分所有者の、国内管理人の届出</span><span class="state" style="color:var(--ok)">✓ 改定案に入れる（11月3日 21:38 保存）</span><span class="open">詳しく ▾</span></div></div>
<div class="row ref"><div class="rh"><span class="lab ref">参考</span><span class="tt">古い用語「マンション敷地売却」の言い換え</span><span class="state" style="color:var(--ink2)">あとで決める</span><span class="open">詳しく ▾</span></div></div>
"""


def decide(sp=False) -> str:
    """ステップ2：指摘の判断。"""
    summary = ('<div class="sum" data-n="6"><b style="font-size:20px">法律で必要な 7件 は、もう改定案に入っています。</b><br>'
               'このステップで決めていただくのは、残りの <b>17件</b>（推奨15・参考2）です。　<b>判断済み 5 ／ 17</b>'
               '<div class="bar"><i style="width:29%"></i></div></div>')
    chips = ('<div class="chips" data-n="7"><span class="on">決めること 17</span><span>必須 7（入っています）</span><span>推奨 15</span><span>参考 2</span><span>あとで決める 12</span></div>'
             '<div class="bulk" data-n="11"><b>まとめて判断：</b>委員会でまとめて決めたときは <u>推奨の 15件 をまとめて「改定案に入れる」</u> など、一度に決められます</div>')
    nxt = ('<div class="next" data-n="8"><div class="t"><b>判断済み 5 ／ 17</b>　残りは「あとで決める」のままでも進めます（あとで変えられます）</div>'
           '<span class="btn">判断を終えて、改定案を作る →</span></div>')
    if sp:
        body = (header(True) + '<div class="wrap" style="padding:10px 12px 140px">' + kairan(1, True)
                + '<div class="step">ステップ 2 / 6</div><h1 style="font-size:24px">指摘を判断する</h1>'
                + summary.replace('<br>', '<br>').replace('　<b>判断済み', '<br><b>判断済み')
                + '<div class="chips" data-n="7"><span class="on">決めること 17</span><span>必須 7</span><span>推奨 15</span></div>'
                + ROWS_HTML.replace('margin:4px 0 0 64px', 'margin:4px 0 0 0').replace('class="rh"', 'class="rh" style="flex-wrap:wrap;gap:6px"')
                .replace('grid-template-columns:repeat(3,1fr)', 'grid-template-columns:1fr')
                + '</div><div class="next" data-n="8" style="padding:10px 12px"><span class="btn" style="flex:1">判断を終えて、改定案へ →</span></div>')
        body = body.replace('.choice{', '.choice{')
        return page(body.replace('<div class="choice"', '<div class="choice" style="grid-template-columns:1fr"').replace('<div class="reason"', '<div class="reason" style="flex-wrap:wrap"'), 390)
    body = (header() + '<div class="wrap">' + kairan(1) + '<div class="step">ステップ 2 / 6</div><h1>指摘を判断する</h1>'
            + summary + chips + ROWS_HTML + '</div>' + nxt)
    return page(body)


def draft() -> str:
    """ステップ3：改定案ができたあと。"""
    body = (header() + '<div class="wrap">' + kairan(2) + '<div class="step">ステップ 3 / 6</div><h1>改定案を確かめる</h1>'
            '<div class="sum" data-n="6"><span class="okline">✓ 改定案ができました</span>　改定 <b>20条</b>（規約 18条＝総会の特別決議、細則 2条＝総会の普通決議）　作成 8分</div>'
            '<div class="card" data-n="9"><b style="font-size:20px">確かめた結果</b>'
            '<ul class="list"><li>プログラムの確認（条番号・参照・数値など 5項目）：<b style="color:var(--ok)">問題なし</b></li>'
            '<li>別の AI の確認（11項目）：<b style="color:var(--ok)">合格</b>（1回目で合格）　<span class="open">確認した項目を見る ▾</span></li></ul></div>'
            '<div class="card" data-n="10"><b style="font-size:20px">人が確かめること（理事会の前に）</b>'
            '<ul class="list"><li>「新旧対照表」で、直した文が委員会の意図どおりか</li>'
            '<li>組合が選ぶ点（〔選択〕）が <b>4か所</b> あります。<b>次の「理事会で検討」</b>で、どちらの案にするか選びます</li></ul>'
            '<div style="margin-top:10px;display:flex;gap:10px"><span class="btn ghost">新旧対照表を開く（印刷できます）</span><span class="btn ghost">指摘の判断に戻る</span></div></div>'
            '</div><div class="next" data-n="8"><div class="t"><b>次は、理事会での検討です</b>　検討資料（印刷用）を作り、議題ごとに判断を記録します</div>'
            '<span class="btn">理事会の検討資料を作る →</span></div>')
    return page(body)


def meeting() -> str:
    """ステップ6：総会の結果と最新の規約。可決の判子は、人が記録した結果だけ。"""
    stamp = '<span class="seal" data-n="14" style="width:96px;height:96px;font-size:30px;border-width:5px">可決</span>'
    body = (header() + '<div class="wrap">' + kairan(5) + '<div class="step">ステップ 6 / 6</div><h1>総会の結果と、最新の規約</h1>'
            '<div class="sum" data-n="6">総会の結果を記録すると、可決した改定を反映した <b>最新の規約</b> を作ります（AI は使いません）。</div>'
            f'<div class="agenda"><div><b style="font-size:20px">第1号議案　管理規約の改定</b><div class="one">改定 18条　／　総会の特別決議</div></div>{stamp}</div>'
            '<div class="agenda"><div><b style="font-size:20px">第2号議案　総会運営細則の改定</b><div class="one">改定 2条　／　総会の普通決議</div></div>'
            '<span class="seal" style="width:96px;height:96px;font-size:30px;border-width:5px;transform:rotate(6deg)">可決</span></div>'
            '<div class="card" style="display:flex;align-items:center;justify-content:space-between"><div><b style="font-size:20px">さくら台マンション管理規約（架空）　最新版</b>'
            '<div class="one">令和8年5月24日 第25期定期総会で改正（附則つき）</div></div><span class="btn">Word でダウンロード</span></div>'
            '<div style="text-align:center;color:var(--ink2);font-size:14px;margin-top:10px">出力は「総会提案の下書き」であり、法的助言ではありません。</div></div>')
    return page(body)


SCREENS = {"v2_decide": decide(), "v2_decide_sp": decide(sp=True), "v2_draft": draft(), "v2_meeting": meeting()}
for name, html in SCREENS.items():
    (OUT / f"{name}.html").write_text(html, encoding="utf-8")

# 説明（番号 → つまずいた点と、その答え）
NOTES = {
    1: ("見出しを見ても、何の論点か分からない", "題名を平易な言葉にし、すぐ下に「何が変わるか」を一文で出す"),
    2: ("判断を保存しても、何が起きたか分からない。保存のたびにページが飛ぶ", "カードの中で「何から何に変えるか」と保存の結果を出す。ページは動かない"),
    3: ("理由を書くタイミングが難しい", "これまでどおり「選ぶ → 理由 → 確定する」。判断を変えるたびに履歴を残す"),
    4: ("必須・推奨・参考が混ざり、色の違いも分かりにくい", "区分は色に加えて文字のラベルと左の太い線で示す。必須はもう入っていると1行で示す"),
    5: ("「採用」「保留」など内部の言葉が分かりにくい", "見た目は「改定案に入れる／今回は見送る／あとで決める」。保存する値は今のまま"),
    6: ("何件あって、何をすればよいか分からない", "各ステップの冒頭に要約：入っている件数、決める件数、判断済みの件数"),
    7: ("一覧が長く、区分ごとに見たい", "絞り込みは残し、最初は「決めること」だけを表示する"),
    8: ("改定案ができても次へ進まない。次に何をするか分からない", "画面の下に、次の一手のボタンを1つだけ固定する"),
    9: ("確認の結果が「satisfied」の英語だけ", "日本語だけで「合格（1回目で合格）」。項目は開いて読む"),
    10: ("「選ぶ必要があります」のあと、どこで選ぶのか分からない", "どのステップで選ぶかを、件数とともに書く"),
    11: ("推奨・参考を1件ずつ判断する手間", "まとめて判断を、要約のすぐ下に置く"),
    12: ("ページが長い（約8,000px）。どこまで進んだか分からない", "ステップごとの画面に分け、上に回覧板の押印欄。人が判断した段は「済」の判子、AI の段は ✓"),
    13: ("年配の理事には文字が小さい", "「文字を大きく」を常に置く。本文18px、押す場所は高さ44px以上"),
    14: ("（日本らしさ）", "「可決」の判子は、人が記録した総会の結果にだけ押す"),
}
(OUT / "notes.json").write_text(__import__("json").dumps(NOTES, ensure_ascii=False), encoding="utf-8")
print("作成：", ", ".join(SCREENS))
