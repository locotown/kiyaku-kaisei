// デモ動画の画面録画（場面ごとに1本）。
// 11/8 v3：文字をくっきり見せるため、1920×900 の画面に、ページを 1.5 倍（CSS の zoom）で表示して録る。
//   見え方は 1280×600 の画面と同じで、画素が 1.5 倍になる（edit.py では、そのまま上の900pxに置く）。
//   録画は Chrome の screencast（JPEG の連番）→ ffmpeg で 30fps の mp4（clips/<名前>.mp4）。
// offsets.json に「画面が整った時刻」（録画の始まりからの秒）を残し、編集でそこから切り出す。
//
// 使い方：node docs/demo/video/record.js [場面の名前 ...]（名前を省くと全部）
//   撮影用のサーバー（KIYAKU_DATA_DIR を撮影用に分けたもの）を BASE で指す。作業の ID は ids_v3.json（prep_v3.py が作る）
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const BASE = process.env.BASE || 'http://127.0.0.1:8800';
const IDS = JSON.parse(fs.readFileSync(path.join(__dirname, 'ids_v3.json')));
const W = key => `${BASE}/works/${IDS[key]}`;
const OUT = path.join(__dirname, 'clips');
const ZOOM = 1.5;
fs.mkdirSync(OUT, { recursive: true });
const offFile = path.join(__dirname, 'offsets.json');
const offsets = fs.existsSync(offFile) ? JSON.parse(fs.readFileSync(offFile)) : {};
const sleep = ms => new Promise(r => setTimeout(r, ms));

// ページ内の座標（CSS の px）。zoom の中では getBoundingClientRect が拡大後の値を返すので、ZOOM で割って揃える
async function smooth(page, dy, ms) {  // なめらかにスクロール（dy はページの px）
  await page.evaluate(([dy, ms]) => new Promise(res => {
    const y0 = window.scrollY, t0 = performance.now();
    function step(t) { const k = Math.min((t - t0) / ms, 1); const e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      window.scrollTo(0, y0 + dy * e); if (k < 1) requestAnimationFrame(step); else res(); }
    requestAnimationFrame(step);
  }), [dy, ms]);
}
async function topOf(page, sel) {  // 要素の上端が、いまの画面の上から何 px か（スクロールの単位）
  return page.$eval(sel, e => {
    const y0 = window.scrollY; e.scrollIntoView({ block: 'start' }); const y1 = window.scrollY; window.scrollTo(0, y0); return y1 - y0;
  });
}
async function scrollTo(page, sel, ms, margin = 90) {  // 要素の上端を、画面の上から margin（ページの px）の位置へ
  const dy = await topOf(page, sel);
  await smooth(page, dy - margin, ms);
}

async function clip(name, fn) {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 900 }, locale: 'ja-JP', timezoneId: 'Asia/Tokyo' });
  await ctx.addInitScript(z => { document.addEventListener('DOMContentLoaded', () => { document.documentElement.style.zoom = String(z); }); }, ZOOM);
  const page = await ctx.newPage();
  page.on('dialog', d => d.accept());
  const cdp = await ctx.newCDPSession(page);
  const frames = [];
  cdp.on('Page.screencastFrame', async f => {
    frames.push({ t: f.metadata.timestamp, d: f.data });
    try { await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }); } catch (e) {}
  });
  await page.goto(BASE + '/healthz');
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 94, maxWidth: 1920, maxHeight: 900, everyNthFrame: 1 });
  await sleep(300);
  const t0 = Date.now() / 1000;
  await fn(page, () => { offsets[name] = +(Date.now() / 1000 - t0).toFixed(2); });
  await sleep(800);
  await cdp.send('Page.stopScreencast');
  const t1 = Date.now() / 1000;
  await browser.close();
  // 連番の JPEG を、表示された時間どおりにつなぐ（最初のフレームを録画の始まり t0 に合わせる）
  const dir = path.join(OUT, '_' + name);
  fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir);
  const fr = frames.filter(f => f.t >= t0 - 1);
  let list = '';
  fr.forEach((f, i) => {
    const fn = path.join(dir, `f${String(i).padStart(5, '0')}.jpg`);
    fs.writeFileSync(fn, Buffer.from(f.d, 'base64'));
    const start = i === 0 ? t0 : f.t;
    const end = i + 1 < fr.length ? fr[i + 1].t : t1;
    list += `file '${fn}'\nduration ${Math.max(end - start, 0.001).toFixed(4)}\n`;
  });
  list += `file '${path.join(dir, `f${String(fr.length - 1).padStart(5, '0')}.jpg`)}'\n`;
  fs.writeFileSync(path.join(dir, 'list.txt'), list);
  execFileSync('ffmpeg', ['-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', path.join(dir, 'list.txt'),
    '-vf', 'scale=1920:900:flags=lanczos,fps=30,format=yuv420p', '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', path.join(OUT, name + '.mp4')]);
  fs.rmSync(dir, { recursive: true, force: true });
  fs.writeFileSync(offFile, JSON.stringify(offsets, null, 2));
  console.log(name, '整った時刻', offsets[name], '秒・長さ', (t1 - t0).toFixed(1), '秒・コマ', fr.length);
}

const SCENES = {
  // ③ 0:38 トップ画面。Word の規約集を読み込む（送信はしない。実際の作業はサンプル「Word の規約集（架空）」から作った）
  c1_upload: async (p, ready) => {
    await p.goto(BASE + '/'); await sleep(900); ready();
    await sleep(500);
    await p.type('#name', '2026年度 規約見直し', { delay: 70 });
    await p.type('#org', 'さくら台マンション管理組合（架空）', { delay: 45 });
    await p.setInputFiles('#file', path.resolve(__dirname, '../../../evals/data/old_collection.docx')); await sleep(500);
    await p.selectOption('#version', 'はい'); await sleep(300);
    await scrollTo(p, '#electronic', 1300, 330);
    await p.selectOption('#electronic', '未定'); await sleep(900);
    await scrollTo(p, 'form[action="/works"] button.btn', 900, 380);
    await p.hover('form[action="/works"] button.btn'); await sleep(1800);
  },
  // ③ 0:44 点検の進み具合（実際の点検の記録。早送りの表示は編集で重ねる）
  c2_review_busy: async (p, ready) => {
    await p.goto(W('review_busy')); await sleep(1500); ready();
    await sleep(1500); await scrollTo(p, '.progress, #progress, .busybox', 1500, 40).catch(() => {}); await sleep(9000);
  },
  // ③ 0:52 指摘の一覧。必須の指摘と、根拠の条文
  c3_findings: async (p, ready) => {
    await p.goto(W('decided') + '#findings'); await sleep(1200); ready();
    await sleep(1200);
    await p.click('#sec-must > summary'); await sleep(900);
    await scrollTo(p, '#sec-must', 1500, 70); await sleep(900);
    await p.click('#sec-must .fcard >> nth=0 >> summary'); await sleep(1200);
    await scrollTo(p, '#sec-must .fcard >> nth=0', 1200, 60); await sleep(1500);
    await scrollTo(p, '#sec-must .fcard:first-of-type .basis', 1500, 220); await sleep(700);
    await p.click('#sec-must .fcard:first-of-type .basis summary >> nth=0'); await sleep(3200);
  },
  // ③ 1:00 理事会のメンバーと相談して、推奨を「改定案に入れる」
  c4_basis_bulk: async (p, ready) => {
    await p.goto(W('reviewed') + '#findings'); await sleep(1200); ready();
    await sleep(800);
    await scrollTo(p, 'details.glossary', 1200, 140);
    await p.click('details.glossary > summary'); await sleep(2600);
    await scrollTo(p, '#f-2', 1500, 90);
    await p.click('#f-2 > summary'); await sleep(1200);
    await scrollTo(p, '#db-2', 1000, 200);
    await p.click('#db-2 label.c-採用'); await sleep(900);
    await p.type('#rs-2', '理事会で相談し、標準管理規約にそろえる', { delay: 60 }); await sleep(400);
    await p.click('[data-confirm="2"]'); await sleep(2500);
  },
  // ③ 1:07 改定案の作成（実際の記録。早送りの表示は編集で重ねる）
  c5_draft_busy: async (p, ready) => {
    await p.goto(W('draft_busy')); await sleep(1500); ready();
    await sleep(1500); await sleep(9000);
  },
  // ③ 1:17 新旧対照表（現行の列に今の規約の見出し）
  c7_taisho: async (p, ready) => {
    await p.goto(W('final') + '/taisho'); await sleep(1500); ready();
    await sleep(1800);
    await smooth(p, 700, 6000); await sleep(1500); await smooth(p, 500, 4000); await sleep(1500);
  },
  // ③ 1:26 理事会の欄。組合が選ぶ点（〔選択〕）を選び、対象の条だけ作り直す
  c8_questions: async (p, ready) => {
    await p.goto(W('board') + '#questions'); await sleep(1500); ready();
    await sleep(1500);
    const n = await p.$$eval('#questions [id^="q-"]', qs => qs.length);
    for (let k = 0; k < n; k++) {
      await scrollTo(p, `#q-${k}`, 900, 110);
      const rs = await p.$$(`#q-${k} input[type=radio]`);
      if (rs.length) { await rs[0].check(); await sleep(1300); }
    }
    await scrollTo(p, '#redraftform', 1200, 260).catch(() => {});
    await p.hover('#redraftform button').catch(() => {}); await sleep(2500);
  },
  // ③ 1:35 住民向けの説明（暮らしの言葉で）
  c10_explain: async (p, ready) => {
    await p.goto(W('final') + '/explain'); await sleep(1500); ready();
    await sleep(2000); await smooth(p, 600, 5000); await sleep(1500); await smooth(p, 600, 5000); await sleep(2000);
  },
  // ③ 1:56 最新の規約（附則まで）
  c12_final: async (p, ready) => {
    await p.goto(W('final') + '/final/0/view'); await sleep(1500); ready();
    await sleep(1500); await smooth(p, 700, 5000); await sleep(1500);
    await p.evaluate(() => window.scrollTo(0, document.body.scrollHeight)); await sleep(300);
    await smooth(p, -500, 2500); await sleep(2500);
  },
};

(async () => {
  const want = process.argv.slice(2);
  for (const [name, fn] of Object.entries(SCENES)) {
    if (want.length && !want.includes(name)) continue;
    await clip(name, fn);
  }
})();
