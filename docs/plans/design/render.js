// ラフ案の HTML を PNG に書き出し、比較用の1枚にまとめる材料を作る
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');
(async () => {
  const b = await chromium.launch();
  for (const f of fs.readdirSync(__dirname).filter(f => f.endsWith('.html')).sort()) {
    const sp = f.includes('_sp');
    const p = await b.newPage({ viewport: { width: sp ? 390 : 1280, height: sp ? 844 : 800 } });
    await p.goto('file://' + path.join(__dirname, f)); await p.evaluate(() => document.fonts.ready); await p.waitForTimeout(300);
    await p.screenshot({ path: path.join(__dirname, f.replace('.html', '.png')) });
    await p.close();
  }
  await b.close(); console.log('書き出し完了');
})();
