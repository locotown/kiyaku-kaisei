// デモ動画の図を 1920×1080 の PNG に書き出す。 使い方: node docs/demo/figures/render.js
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const SRC = path.join(__dirname, 'src');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  for (const f of fs.readdirSync(SRC).filter(f => f.endsWith('.html')).sort()) {
    await page.goto('file://' + path.join(SRC, f));
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(300);
    const overflow = await page.evaluate(() => [...document.querySelectorAll('body *')]
      .filter(e => { const r = e.getBoundingClientRect(); return r.right > 1920 || r.bottom > 1080; }).map(e => e.className || e.tagName));
    if (overflow.length) console.log(f, 'はみ出し:', overflow.join(', '));
    await page.screenshot({ path: path.join(__dirname, f.replace('.html', '.png')) });
    console.log('書き出し', f);
  }
  await browser.close();
})();
