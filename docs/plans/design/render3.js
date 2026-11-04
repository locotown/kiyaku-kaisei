// 第3案のラフ案を書き出す
const { chromium } = require('playwright');
const path = require('path');
const V = path.join(__dirname, 'v3');
(async () => {
  const b = await chromium.launch();
  for (const [n, w, h] of [['v3_decide', 1280, 1180], ['v3_decide_sp', 390, 1500], ['v3_draft', 1280, 900], ['v3_meeting', 1280, 900]]) {
    const p = await b.newPage({ viewport: { width: w, height: h } });
    await p.goto('file://' + path.join(V, n + '.html')); await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(400);
    await p.screenshot({ path: path.join(V, n + '.png') }); await p.close();
  }
  await b.close(); console.log('書き出し完了');
})();
