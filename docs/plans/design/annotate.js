// 第2案のラフ案に、画面の外から番号と説明を付けた「説明つきの画像」を作る
// 使い方: node docs/plans/design/annotate.js
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');
const V = path.join(__dirname, 'v2');
const NOTES = JSON.parse(fs.readFileSync(path.join(V, 'notes.json'), 'utf-8'));
const F = 'https://cdn.jsdelivr.net/npm/@fontsource/noto-sans-jp@5.0.19/files/noto-sans-jp-japanese-';
const SCREENS = [['v2_decide', 1280, 1180, 'ステップ2：指摘を判断する（パソコン）'], ['v2_decide_sp', 390, 1500, 'ステップ2：スマホの幅'],
                 ['v2_draft', 1280, 820, 'ステップ3：改定案を確かめる'], ['v2_meeting', 1280, 820, 'ステップ6：総会の結果と最新の規約']];
(async () => {
  const b = await chromium.launch();
  for (const [name, w, h, title] of SCREENS) {
    const p = await b.newPage({ viewport: { width: w, height: h } });
    await p.goto('file://' + path.join(V, name + '.html')); await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(300);
    const marks = await p.$$eval('[data-n]', els => els.map(e => { const r = e.getBoundingClientRect(); return { n: e.dataset.n, y: r.top + r.height / 2, x: r.left, w: r.width }; }));
    await p.screenshot({ path: path.join(V, name + '.png') });
    await p.close();
    // 画面の左右の余白に番号を置き、右側に説明の一覧を並べる
    const seen = new Set(); const uniq = marks.filter(m => !seen.has(m.n) && seen.add(m.n));
    const scale = w > 400 ? 0.62 : 0.7; const iw = w * scale, ih = h * scale;
    uniq.sort((a, c) => a.y - c.y);
    let last = -100; const tops = uniq.map(m => { const t = Math.max(Math.min(m.y, h) * scale - 16, last + 36); last = t; return t; });
    const pins = uniq.map((m, k) => `<div class="pin" style="top:${tops[k]}px;left:${8}px">${m.n}</div>`).join('');
    const list = uniq.map(m => `<li><span class="num">${m.n}</span><div><div class="q">${NOTES[m.n][0]}</div><div class="a">→ ${NOTES[m.n][1]}</div></div></li>`).join('');
    const html = `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:N;font-weight:400;src:url(${F}400-normal.woff2)}@font-face{font-family:N;font-weight:700;src:url(${F}700-normal.woff2)}
body{margin:0;font-family:N;background:#fff;width:${iw + 60 + 760}px}.t{font-weight:700;font-size:26px;padding:8px 14px}
.wrap{position:relative;display:flex;gap:24px}.shot{margin-left:52px;border:1px solid #ccc;width:${iw}px;height:${ih}px}
.pin{position:absolute;width:32px;height:32px;border-radius:50%;background:#c8102e;color:#fff;font-weight:700;font-size:17px;display:flex;align-items:center;justify-content:center}
ul{list-style:none;padding:0;margin:0;width:720px}li{display:flex;gap:10px;margin-bottom:12px}.num{flex:none;width:30px;height:30px;border-radius:50%;background:#c8102e;color:#fff;font-weight:700;display:flex;align-items:center;justify-content:center}
.q{font-size:16px;color:#555}.a{font-size:18px;font-weight:700;color:#111}</style></head><body><div class="t">${title}</div>
<div class="wrap"><img class="shot" src="${name}.png">${pins}<ul>${list}</ul></div></body></html>`;
    fs.writeFileSync(path.join(V, name + '_board.html'), html);
    const q = await b.newPage({ viewport: { width: Math.ceil(iw + 60 + 760), height: 400 } });
    await q.goto('file://' + path.join(V, name + '_board.html')); await q.evaluate(() => document.fonts.ready); await q.waitForTimeout(300);
    await q.screenshot({ path: path.join(V, name + '_説明つき.png'), fullPage: true }); await q.close();
  }
  await b.close(); console.log('書き出し完了');
})();
