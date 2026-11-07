"""印刷用の資料（新旧対照表・理事会の検討資料・住民向けの説明・最新の規約）に共通の見た目。

資料は private/work/<id>/ に単独の HTML として保存され、ネットにつながらない環境でも開くので、
CSS はファイルに埋め込む。値は app/static/tokens.css（デザインシステムの正本）の写し。
トークンを変えたら、ここも合わせる（docs/DESIGN_SYSTEM.md）。判子は使わない（人が記録した結果ではないため）。
"""

import re

PRINT_CSS = """
@import url("https://fonts.googleapis.com/css2?family=BIZ+UDPGothic:wght@400;700&display=swap");
:root {
  --color-bg: #f6f5f2; --color-surface: #ffffff;
  --color-ink: #1b1d20; --color-ink-2: #474c53; --color-ink-3: #61666d;
  --color-line: #e2dfd8; --color-line-2: #cfcbc2;
  --color-primary: #24456b; --color-primary-soft: #edf1f6;
  --color-must: #9a3324; --color-rec: #2b4f7a; --color-ref: #5d6167; --color-ok: #2d6a4f;
  --font-sans: "BIZ UDPGothic", "Hiragino Sans", "Noto Sans JP", "Yu Gothic", sans-serif;
}
* { box-sizing: border-box; }
body { font-family: var(--font-sans); max-width: 820px; margin: 32px auto; padding: 0 24px; line-height: 1.8;
       color: var(--color-ink); background: var(--color-surface); font-size: 17px; -webkit-font-smoothing: antialiased; }
body.wide { max-width: none; margin: 32px; padding: 0; }
h1, h2, h3, h4 { font-feature-settings: "palt"; line-height: 1.4; font-weight: 700; }
/* 日本語の組み方：行の右端まで文字を詰め（禁則処理つき）、文章は両端をそろえる */
body { line-break: strict; }
p, li, .note { text-align: justify; }
h1, h2, h3, h4 { text-wrap: balance; }
h1 { font-size: 1.6rem; margin: 0 0 16px; padding-bottom: 12px; border-bottom: 2px solid var(--color-primary); }
h2 { font-size: 1.25rem; margin: 2em 0 .4em; }
h3, h3.title { font-size: 1.1rem; margin: 1.4em 0 .2em; }
h4 { font-size: 1rem; color: var(--color-primary); margin: .9em 0 .1em; }
p { margin: 0 0 .8em; }
ul { margin: .2em 0 .6em; padding-left: 1.4em; }
.arts { font-size: .85rem; color: var(--color-ink-3); margin: 0 0 .4em; }

/* 3段の区分：色の見出しと左の線（色の付いた箱にしない） */
.tier { margin-top: 2.4em; padding: 4px 0 4px 16px; border-left: 3px solid var(--color-line-2); }
.tier h2 { margin: .1em 0 .1em; }
.tier p { margin: 0 0 .4em; font-size: .92rem; color: var(--color-ink-2); }
.tier1 { border-left-color: var(--color-must); } .tier1 h2 { color: var(--color-must); }
.tier2 { border-left-color: var(--color-rec); } .tier2 h2 { color: var(--color-rec); }
.tier3 { border-left-color: var(--color-ref); } .tier3 h2 { color: var(--color-ref); }
.item { border-top: 1px solid var(--color-line); padding-top: 4px; }

/* 理事会の検討資料 */
.decide { font-size: .92rem; border-top: 1px dashed var(--color-line-2); padding: 6px 0 0; margin-top: .6em; }
.rec { font-size: .92rem; color: var(--color-ok); }
.choose { border-left: 3px solid var(--color-line-2); padding: 2px 0 2px 16px; margin: .8em 0; }
.choose ul { list-style: none; padding-left: .4em; }
.cnote { font-size: .85rem; color: var(--color-ink-2); }

/* 住民向けの説明 */
.box { border-top: 1px solid var(--color-line-2); border-bottom: 1px solid var(--color-line-2); padding: 8px 0; }
table.list { border-collapse: collapse; width: 100%; font-size: .85rem; }
table.list th, table.list td { border-bottom: 1px solid var(--color-line); padding: 6px 8px 6px 0; text-align: left; vertical-align: top; }
table.list th { color: var(--color-ink-3); font-size: .8rem; border-bottom-color: var(--color-line-2); }

/* 区分などの札：色の文字と左の細い線（丸い札にしない） */
.tag { display: inline-block; font-size: .8rem; font-weight: 700; line-height: 1.3; padding: 0 0 0 8px; margin: 2px 8px 2px 0;
       border-left: 3px solid currentColor; color: var(--color-primary); background: none; border-radius: 0; }
.tag.must { color: var(--color-must); } .tag.opt { color: var(--color-rec); }
.t-新設 { color: var(--color-ok); } .t-削除 { color: var(--color-ref); } .t-附則 { color: var(--color-primary); }

/* 注記：線で区切る（黄色い箱にしない） */
.note { font-size: .88rem; color: var(--color-ink-2); border-left: 3px solid var(--color-line-2); padding: 4px 0 4px 14px; margin: 1.2em 0; }
.legend, .summary { font-size: .92rem; color: var(--color-ink-2); }
.topics { font-size: .8rem; color: var(--color-ink-2); margin-bottom: 6px; }

/* 新旧対照表 */
body.wide table { border-collapse: collapse; width: 100%; table-layout: fixed; }
body.wide th, body.wide td { border: 1px solid var(--color-line-2); padding: 10px; vertical-align: top; font-size: .92rem; word-break: break-all; }
body.wide th { background: var(--color-bg); font-size: .85rem; color: var(--color-ink-2); text-align: left; }
body.wide th:nth-child(1) { width: 37%; } body.wide th:nth-child(2) { width: 33%; }
body.wide td:nth-child(3) { font-size: .85rem; color: var(--color-ink-2); }
body.wide h2 { border-left: 3px solid var(--color-primary); padding-left: 10px; }
tr.row-must td:first-child { box-shadow: inset 3px 0 0 var(--color-must); }
tr.row-opt td:first-child { box-shadow: inset 3px 0 0 var(--color-line-2); }
mark { background: var(--color-primary-soft); color: inherit; padding: 0 1px; text-decoration: underline; text-decoration-color: var(--color-primary); text-underline-offset: 3px; }
del { color: var(--color-must); text-decoration-color: var(--color-must); text-decoration-thickness: 1.5px; }
.refcap { color: var(--color-ink-2); font-size: .9em; }
.humanedit { display: block; width: fit-content; font-size: .8rem; font-weight: 700; color: var(--color-must); border: 1px solid var(--color-must); border-radius: 4px; padding: 0 6px; margin-bottom: 4px; }
.humanedit.ok { color: var(--color-ok); border-color: var(--color-ok); }
tr.row-skip td { background: #f1f0ec; color: var(--color-ink-2); }
.skipmark { display: block; width: fit-content; font-size: .8rem; font-weight: 700; color: var(--color-must); border: 1px dashed var(--color-must); border-radius: 4px; padding: 0 6px; margin-bottom: 4px; }
.editnote { margin-top: 6px; padding: 4px 6px; border-left: 3px solid var(--color-must); background: #fff6f3; white-space: pre-line; }
.rowno { display: block; font-weight: 700; color: var(--color-primary); font-size: .9rem; margin-bottom: 2px; }

/* 最新の規約：変更した条は左の線で示す */
.art { margin: .7em 0; padding: 2px 0 2px 14px; border-left: 3px solid transparent; }
.art.ch { border-left-color: var(--color-primary); background: none; }

/* 画面だけに出す操作の帯（印刷する・Word で保存）。印刷には出ない */
.toolbar { position: sticky; top: 0; z-index: 10; display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center;
           padding: 10px 0; margin: -8px 0 16px; background: var(--color-surface); border-bottom: 1px solid var(--color-line); font-size: .9rem; }
.toolbar button, .toolbar a { font: inherit; font-weight: 700; min-height: 40px; display: inline-flex; align-items: center; padding: 0 16px;
           border-radius: 6px; text-decoration: none; cursor: pointer; }
.toolbar button { background: var(--color-primary); color: #fff; border: 0; }
.toolbar a { color: var(--color-primary); border: 1px solid var(--color-line-2); background: var(--color-surface); }
.toolbar .hint { color: var(--color-ink-3); font-size: .85rem; }
.toolbar .safari { flex-basis: 100%; margin: 0; color: var(--color-must); font-weight: 700; font-size: .9rem; }

h1, h2, h3, h4 { text-align: left; }
/* スマホ：新旧対照表は条ごとのカード（改定案／現行／理由）に並べ替える。帯は固定せず、印刷の説明は畳む */
@media screen and (max-width: 720px) {
  p, li, .note { text-align: left; }
  .toolbar { position: static; padding: 8px 12px; }
  .toolbar .hint, .toolbar .safari { display: none !important; }
  table.taisho, table.taisho tbody, table.taisho tr, table.taisho td { display: block; width: auto !important; }
  table.taisho thead { display: none; }
  table.taisho tr { border: 1px solid var(--color-line-2); border-radius: 6px; margin: 0 0 14px; background: var(--color-surface); }
  table.taisho td { border: 0 !important; border-top: 1px solid var(--color-line) !important; padding: 8px 10px !important; }
  table.taisho td:first-child { border-top: 0 !important; }
  table.taisho td::before { content: attr(data-label); display: block; font-size: .78rem; font-weight: 700; color: var(--color-ink-3); margin-bottom: 2px; }
  tr.row-must td:first-child, tr.row-opt td:first-child { box-shadow: none; }
  tr.row-must { border-left: 4px solid var(--color-must) !important; }
}
@media print {
  .toolbar { display: none !important; }
  /* 新旧対照表：行の番号と本文が別のページに分かれにくくする（写真に行番号が写らない、という声から） */
  table.taisho tr { break-inside: avoid-page; page-break-inside: avoid; }
  h1, h2, h3, h4, .tier, .arts { break-after: avoid-page; }
  thead { display: table-header-group; }
  .check, .cpoint, .decide, .rec, .art { break-inside: avoid; }  /* 表の行は途中で切れてよい（長い条を次のページに送ると大きな空白ができる。見出しは各ページにくり返す） */
  p, li { orphans: 2; widows: 2; }
  body, body.wide { margin: 0; padding: 0; font-size: 11pt; max-width: none; }
  .art.ch { border-left-color: transparent; } .art .tag, body.final .note { display: none; }
  a { color: inherit; text-decoration: none; }
}
"""


def page_css(title: str, landscape: bool = False, ident: str = "") -> str:
    """印刷の用紙（A4。新旧対照表は横）、余白、上の欄の資料名、下の欄のページ番号。

    会議で「何ページの何条」と言えるように、すべてのページに資料名とページ番号を入れる。
    ident（作業と改定案の版の番号）を右上に入れ、書き込んだ紙を戻したときに、どの版の紙かを見分けられるようにする。
    """
    # CSS の文字列に入れるので、\ と " のほか、< > も外す（</style> で抜けてスクリプトが動いた。検証での指摘）
    name = re.sub(r"[\\<>]", "", " ".join(title.split())).replace('"', "”")
    ident = re.sub(r"[\\\"<>]", "", ident or "")
    font = '"BIZ UDPGothic", "Hiragino Sans", "Noto Sans JP", "Yu Gothic", sans-serif'
    return f"""
@page {{
  size: A4{" landscape" if landscape else ""}; margin: 16mm 14mm 16mm;
  @top-left {{ content: "{name}"; font-family: {font}; font-size: 8pt; color: #61666d; }}
  @top-right {{ content: "総会提案の下書き{('　' + ident) if ident else ''}"; font-family: {font}; font-size: 8pt; color: #61666d; }}
  @bottom-center {{ content: counter(page) " / " counter(pages); font-family: {font}; font-size: 9pt; color: #474c53; }}
}}
"""


def toolbar(word_href: str = "", landscape: bool = False, back_href: str = "./") -> str:
    """画面の上に出す操作の帯（作業の画面に戻る・印刷する・Word で保存）。印刷には出ない。

    スマホでは、印刷の説明を畳み、帯を上に固定しない（画面の4分の1を占めて読みにくい、という声から）。
    """
    word = f'<a href="{word_href}">Word で保存（直して使う）</a>' if word_href else ""
    # 作業の画面から開いたときは、開いたときの画面（ステップ・位置）に戻る。ほかから開いたときは、資料を作ったステップへ
    # （新旧対照表から戻るとステップ4になり混乱した。確認ボード 第20回の気づき）
    back = (f'<a href="{back_href}" class="back" onclick="if (document.referrer.indexOf(location.origin + \'/works/\') === 0 '
            f'&amp;&amp; history.length > 1) {{ history.back(); return false; }}">← 作業の画面に戻る</a>') if back_href else ""
    paper = "A4 横" if landscape else "A4 縦"
    return (f'<div class="toolbar">{back}<button type="button" onclick="window.print()">印刷する</button>{word}'
            '<p class="safari" hidden>Safari では、各ページの上下に資料名・版の番号・ページ番号が出ません。'
            'Chrome か Edge で開いて印刷してください。</p>'
            '<script>if (/^((?!chrome|chromium|crios|fxios|edg|android).)*safari/i.test(navigator.userAgent))'
            ' document.querySelector(".toolbar .safari").hidden = false;</script>'
            f'<span class="hint">{paper}で印刷します（Chrome か Edge で印刷すると、各ページに資料名とページ番号が入ります）。'
            '変更箇所の色も印刷するには、印刷の設定で「背景のグラフィック」をオンにしてください。'
            '会議で書き込むときは、赤など色の付いたペンで書くと、写真から読み取りやすくなります。</span></div>')
