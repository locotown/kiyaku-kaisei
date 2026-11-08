// デモ動画の図を 1920×1080 の PNG に書き出す。 使い方: node docs/demo/figures/render.js [図の名前 ...]
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const SRC = path.join(__dirname, 'src');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  const only = process.argv.slice(2);  // 名前を渡すと、その図だけ書き出す（例：node render.js 04_eval 09_end）
  for (const f of fs.readdirSync(SRC).filter(f => f.endsWith('.html') && (!only.length || only.includes(f.replace('.html', '')))).sort()) {
    await page.goto('file://' + path.join(SRC, f));
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(300);
    const overflow = await page.evaluate(() => [...document.querySelectorAll('body *')]
      .filter(e => !e.closest('svg') && !e.className.includes?.('kari')).filter(e => { const r = e.getBoundingClientRect(); return r.right > 1920 || r.bottom > 1080; }).map(e => e.className || e.tagName));
    if (overflow.length) console.log(f, 'はみ出し:', overflow.join(', '));
    // 判子（07s_*）は背景を透明にして、判子の部分だけ書き出す（動画の編集で重ねる）
    const stamp = f.includes('_stamp_');
    // 団地の絵は、11/8 v3 から「仮」の印を外して書き出す（完成版の動画に仮の印が映らないように。写真への差し替えは docs/demo/video/README.md）
    if (f === '05_danchi.html') await page.addStyleTag({ content: '.kari{display:none!important}' });
    await page.screenshot({ path: path.join(__dirname, f.replace('.html', '.png')), omitBackground: stamp,
                            clip: stamp ? { x: 0, y: 0, width: 520, height: 520 } : undefined });
    console.log('書き出し', f);
    // 締めの画面は、背景の絵を外した版（09_end_fg.png。背景が透明）も作る。作者の写真を背景にするとき、edit.py が重ねる（docs/demo/video/README.md）
    if (f === '09_end.html') {
      await page.addStyleTag({ content: '.bg{display:none!important}html,body{background:transparent!important}' });
      await page.screenshot({ path: path.join(__dirname, '09_end_fg.png'), omitBackground: true });
      console.log('書き出し 09_end_fg.png');
    }
  }
  await browser.close();
})();
