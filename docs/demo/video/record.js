// 仮のデモ動画の画面録画（場面ごとに1本。1280×600：動画では上の900pxに置き、下の帯を字幕に空ける）。offsets.json に「画面が整った時刻」を残し、編集でそこから切り出す
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const BASE = 'http://127.0.0.1:8000';
const D = id => `${BASE}/works/20261103-200000-${id}`;
const OUT = path.join(__dirname, 'clips');
fs.mkdirSync(OUT, { recursive: true });
const offsets = {};
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function smooth(page, dy, ms) {  // なめらかにスクロール
  await page.evaluate(([dy, ms]) => new Promise(res => {
    const y0 = window.scrollY, t0 = performance.now();
    function step(t) { const k = Math.min((t - t0) / ms, 1); const e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      window.scrollTo(0, y0 + dy * e); if (k < 1) requestAnimationFrame(step); else res(); }
    requestAnimationFrame(step);
  }), [dy, ms]);
}
async function scrollTo(page, sel, ms, margin = 90) {
  const y = await page.$eval(sel, e => e.getBoundingClientRect().top);
  await smooth(page, y - margin, ms);
}
async function clip(name, fn) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 600 }, locale: 'ja-JP', recordVideo: { dir: OUT, size: { width: 1280, height: 600 } } });
  const t0 = Date.now();
  const page = await ctx.newPage();
  page.on('dialog', d => d.dismiss());
  await fn(page, () => { offsets[name] = (Date.now() - t0) / 1000; });
  await sleep(600);
  const v = page.video();
  await ctx.close(); await browser.close();
  fs.renameSync(await v.path(), path.join(OUT, name + '.webm'));
  console.log(name, offsets[name]);
}
(async () => {
  await clip('c1_upload', async (p, ready) => {
    await p.goto(BASE + '/'); await sleep(800); ready();
    await sleep(600);
    await p.type('#name', '規約見直し（委員会案）', { delay: 90 });
    await p.type('#org', 'さくら台マンション管理組合（架空）', { delay: 60 });
    await p.setInputFiles('#file', path.resolve(__dirname, '../../../evals/data/old_collection.docx'));
    await scrollTo(p, '#electronic', 1200, 260);
    await p.selectOption('#electronic', '未定'); await sleep(1500);
    await p.hover('text=点検を始める'); await sleep(1500);
  });
  await clip('c2_review_busy', async (p, ready) => {
    await p.goto(D('dm0002')); await sleep(1200); ready();
    await sleep(9000);
  });
  await clip('c3_findings', async (p, ready) => {
    // 11/4 第3案：ステップごとの画面。指摘は1行に畳んであり、押すと開く
    await p.goto(D('dm0001') + '#findings'); await sleep(1000); ready();
    await sleep(1500);
    await p.click('.fbtn[data-filter="必須"]'); await sleep(1500);
    await smooth(p, 420, 2500); await sleep(1000);
    await p.click('.fcard:not([hidden]) > summary'); await sleep(1500);
    await smooth(p, 260, 2000); await sleep(2000);
  });
  await clip('c4_basis_bulk', async (p, ready) => {
    await p.goto(D('dm0001') + '#findings'); await sleep(800);
    try { await p.click('.fbtn[data-filter="必須"]'); } catch (e) {}
    await p.evaluate(() => { const c = document.querySelector('.fcard:not([hidden])'); c.open = true; const b = c.querySelector('.basis'); window.scrollTo(0, b.getBoundingClientRect().top + window.scrollY - 330); });
    await sleep(800); ready();
    await sleep(800);
    await p.click('.fcard:not([hidden]) .basis summary'); await sleep(2800);
    await p.click('.fbtn[data-filter="decide"]'); await sleep(300);
    await scrollTo(p, '#bulk', 1200, 200); await sleep(500);
    await p.click('#bulk > summary'); await sleep(800);
    await p.selectOption('#bk-dec', '採用'); await sleep(1800);
  });
  await clip('c5_draft_busy', async (p, ready) => {
    await p.goto(D('dm0003')); await sleep(1200); ready();
    await sleep(9000);
  });
  await clip('c6_quality', async (p, ready) => {
    await p.goto(D('dm0001') + '?done=' + encodeURIComponent('改定案作成中') + '#next'); await sleep(1000); ready();
    await sleep(2000);
    await smooth(p, 420, 4000); await sleep(1500); await smooth(p, 380, 3500); await sleep(1000);
  });
  await clip('c7_taisho', async (p, ready) => {
    await p.goto(D('dm0001') + '/taisho'); await sleep(1000); ready();
    await sleep(1500);
    await smooth(p, 900, 7000); await sleep(3000);
  });
  await clip('c8_questions', async (p, ready) => {
    await p.goto(D('dm0004') + '#questions'); await sleep(1000); ready();
    await sleep(1500);
    const qs = await p.$$('#questions .cu-point');
    for (let k = 0; k < qs.length; k++) {
      const rs = await p.$$(`input[name="b_q_${k}"]`);
      if (rs.length) { await rs[rs.length - 1].check(); await sleep(1100); }
      if (k === 1) { await smooth(p, 300, 1200); }
    }
    await sleep(2500);
  });
  await clip('c9_board_done', async (p, ready) => {
    await p.goto(D('dm0001') + '#board'); await sleep(1000); ready();
    await sleep(1500); await smooth(p, 500, 3000); await sleep(2000);
  });
  await clip('c10_explain', async (p, ready) => {
    await p.goto(D('dm0001') + '/explain'); await sleep(1000); ready();
    await sleep(2000); await smooth(p, 1100, 8000); await sleep(3000);
  });
  await clip('c11_meeting', async (p, ready) => {
    await p.goto(D('dm0001') + '?done=meeting#meeting'); await sleep(1000); ready();
    await sleep(2000); await smooth(p, 300, 2500); await sleep(2500);
  });
  await clip('c12_final', async (p, ready) => {
    const html = await (await p.request.get(D('dm0001') + '/final/0/view')).text();
    await p.goto(D('dm0001') + '/final/0/view'); await sleep(1000);
    await p.evaluate(() => { const m = document.querySelector('.changed, mark, .chg, [class*=chang]'); if (m) window.scrollTo(0, m.getBoundingClientRect().top + window.scrollY - 200); });
    ready();
    await sleep(1500); await smooth(p, 700, 5000); await sleep(2500);
  });
  fs.writeFileSync(path.join(__dirname, 'offsets.json'), JSON.stringify(offsets, null, 2));
})();
