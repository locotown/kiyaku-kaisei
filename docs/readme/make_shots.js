// README の画面を撮り直す（画面を直したら、これを動かして差し替える）。
// 使うのは公開の架空のサンプル（data/public/persona_works の作業）だけ。実物の規約は撮らない。
//   1. サーバーを起動：uv run uvicorn app.main:app --port 8765
//   2. node docs/readme/make_shots.js
//   相談の画面も撮るときは、架空の質問で作った相談の id を CONSULT_ID に入れる
const { chromium } = require('playwright');
const path = require('path');

const BASE = process.env.BASE || 'http://localhost:8765';
const WORK = process.env.WORK || '20261106-220948-f85ddb';   // 想定ユーザー（架空）の作業：細則を含む規約集（架空）
const OUT = __dirname + path.sep;

(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 1 });
  await p.goto(BASE + '/');                                   // 一覧を開くと、想定ユーザーの作業が写される
  const shot = async (url, name, sel, h) => {
    await p.goto(url); await p.waitForTimeout(700);
    await p.evaluate((s) => { const e = s && document.querySelector(s); if (e) { e.scrollIntoView({ block: 'start' }); window.scrollBy(0, -16); } else window.scrollTo(0, 0); }, sel);
    await p.waitForTimeout(200);
    await p.screenshot({ path: OUT + name, clip: { x: 0, y: 0, width: 1200, height: h } });
    console.log(name);
  };
  const W = `${BASE}/works/${WORK}`;
  await shot(W + '#findings', '01_findings.png', 'p.eyebrow.wk', 900);
  await shot(W + '#board', '02_board.png', 'section[data-step="board"] .stepttl', 900);
  await shot(W + '/taisho', '03_taisho.png', null, 760);
  if (process.env.CONSULT_ID) await shot(`${BASE}/consult/${process.env.CONSULT_ID}`, '04_consult.png', null, 900);
  await b.close();
})();
