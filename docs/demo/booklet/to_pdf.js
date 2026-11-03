// booklet.html を A5 の PDF にする（印刷して冊子にし、手元の撮影に使う）
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://' + path.join(__dirname, 'booklet.html'));
  await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(500);
  await p.pdf({ path: path.join(__dirname, 'sakuradai_kiyaku_kakuu.pdf'), format: 'A5', printBackground: true });
  await b.close(); console.log('PDF を書き出しました');
})();
