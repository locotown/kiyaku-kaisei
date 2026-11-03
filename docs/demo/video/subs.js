// 字幕（日本語のナレーション＋英語）を、背景が透明な 1920×1080 の PNG にする
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');
const rows = JSON.parse(fs.readFileSync(path.join(__dirname, 'rows.json')));
const F = 'https://cdn.jsdelivr.net/npm/@fontsource/noto-sans-jp@5.0.19/files/noto-sans-jp-japanese-';
const esc = t => t.replace(/[<>&]/g, c => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]));
fs.mkdirSync(path.join(__dirname, 'subs'), { recursive: true });
(async () => {
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  for (const [i, r] of rows.entries()) {
    await p.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:N;font-weight:700;src:url(${F}700-normal.woff2)}@font-face{font-family:N;font-weight:400;src:url(${F}400-normal.woff2)}
html,body{margin:0;background:transparent;width:1920px;height:1080px}
.box{position:absolute;left:0;right:0;margin:0 auto;width:fit-content;bottom:36px;max-width:1720px;background:rgba(11,11,11,.72);border-radius:10px;padding:14px 30px 16px;text-align:center;font-family:N}
.jp{color:#fff;font-size:38px;font-weight:700;line-height:1.45}.en{color:#d7d6cf;font-size:24px;font-weight:400;line-height:1.35;margin-top:6px}
</style></head><body><div class="box"><div class="jp">${esc(r.jp)}</div><div class="en">${esc(r.en)}</div></div></body></html>`);
    await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(150);
    await p.screenshot({ path: path.join(__dirname, 'subs', String(i).padStart(2, '0') + '.png'), omitBackground: true });
  }
  // 早送りの表示と、仮編集の印
  for (const [name, text] of [['ff_review', '早送り　実時間 約4分'], ['ff_draft', '早送り　実時間 約10〜20分'], ['kari', '仮編集'], ['booklet', '（仮）手元の撮影に差し替え']]) {
    await p.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>@font-face{font-family:N;font-weight:700;src:url(${F}700-normal.woff2)}
html,body{margin:0;background:transparent;width:1920px;height:1080px}.t{position:absolute;${name === 'kari' ? 'left:28px;top:24px;background:rgba(200,16,46,.85)' : 'right:40px;top:36px;background:rgba(42,120,214,.92)'};color:#fff;font:700 30px N;padding:8px 18px;border-radius:8px}</style></head><body><div class="t">${text}</div></body></html>`);
    await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(150);
    await p.screenshot({ path: path.join(__dirname, 'subs', name + '.png'), omitBackground: true });
  }
  await b.close(); console.log('字幕', rows.length);
})();
