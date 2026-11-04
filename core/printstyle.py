"""印刷用の資料（新旧対照表・理事会の検討資料・住民向けの説明・最新の規約）に共通の見た目。

資料は private/work/<id>/ に単独の HTML として保存され、ネットにつながらない環境でも開くので、
CSS はファイルに埋め込む。値は app/static/tokens.css（デザインシステムの正本）の写し。
トークンを変えたら、ここも合わせる（docs/DESIGN_SYSTEM.md）。判子は使わない（人が記録した結果ではないため）。
"""

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
/* 日本語の折り返し：文節の切れ目で折り返し、行末に1〜2文字だけ残さない（対応していないブラウザは文字単位） */
body { word-break: auto-phrase; text-wrap: pretty; }
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
body.wide td:nth-child(3) { font-size: .85rem; color: var(--color-ink-2); }
body.wide h2 { border-left: 3px solid var(--color-primary); padding-left: 10px; }
tr.row-must td:first-child { box-shadow: inset 3px 0 0 var(--color-must); }
tr.row-opt td:first-child { box-shadow: inset 3px 0 0 var(--color-line-2); }
mark { background: var(--color-primary-soft); color: inherit; padding: 0 1px; text-decoration: underline; text-decoration-color: var(--color-primary); text-underline-offset: 3px; }
del { color: var(--color-must); text-decoration-color: var(--color-must); text-decoration-thickness: 1.5px; }
.refcap { color: var(--color-ink-2); font-size: .9em; }

/* 最新の規約：変更した条は左の線で示す */
.art { margin: .7em 0; padding: 2px 0 2px 14px; border-left: 3px solid transparent; }
.art.ch { border-left-color: var(--color-primary); background: none; }

@media print {
  body, body.wide { margin: 0; padding: 0; font-size: 11pt; max-width: none; }
  .art.ch { border-left-color: transparent; } .art .tag, body.final .note { display: none; }
  a { color: inherit; text-decoration: none; }
}
"""
