// 画面を通しで操作する（架空の規約集 evals/data/old_collection.txt を使う。API を呼ぶので費用がかかる）
// 使い方：画面を起動（uv run uvicorn app.main:app --port 8000）してから
//   node scripts/e2e_demo.js <画面を保存するフォルダ> [続きから再開する作業のURL]
const { chromium } = require('playwright');
const path = require('path');

const BASE = 'http://127.0.0.1:8000';
const SHOT = process.argv[2];
const INPUT = path.resolve(__dirname, '../evals/data/old_collection.txt');
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a);

async function waitStatus(page, url, done, timeoutMin) {
  const end = Date.now() + timeoutMin * 60000;
  let last = '';
  while (Date.now() < end) {
    let s;
    try {
      const r = await page.request.get(url + '/status', { timeout: 30000 });
      s = await r.json();
    } catch (e) {  // 一時的な通信の切断は再試行する
      log('状態の確認に失敗（再試行）:', e.message.split('\n')[0]);
      await new Promise(r => setTimeout(r, 5000));
      continue;
    }
    if (s.status !== last) { log('状態:', s.status); last = s.status; }
    if (done.includes(s.status)) return s.status;
    if (s.status.includes('エラー')) throw new Error('エラー: ' + s.status);
    await new Promise(r => setTimeout(r, 5000));
  }
  throw new Error('時間切れ: ' + last);
}

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, locale: 'ja-JP' });
  const shot = async (name, full = true) => { await page.screenshot({ path: path.join(SHOT, name), fullPage: full }); log('撮影', name); };

  const RESUME = process.argv[3];
  let url;
  if (RESUME) {
    url = RESUME;
    log('続きから再開:', url);
  } else {
  // 1. トップ画面 → 規約集を読み込む
  await page.goto(BASE + '/');
  await shot('01_top.png', false);
  await page.fill('#name', 'デモ：○○マンション（架空）規約見直し');
  await page.setInputFiles('#file', INPUT);
  await page.selectOption('#electronic', '未定');
  await Promise.all([page.waitForURL(/\/works\//), page.click('text=点検を始める')]);
  url = page.url();
  log('作業:', url);
  await page.waitForTimeout(8000);
  await shot('02_reviewing.png', false);
  }

  // 2. 点検の完了を待つ
  await waitStatus(page, url, ['点検済み'], 12);
  await page.goto(url);
  await shot('03_findings.png');

  // 3. 推奨・参考の指摘を採用する（最初の6件は採用、それ以降は保留のまま）
  const selects = await page.$$('select[name^="decision_"]');
  for (let i = 0; i < selects.length; i++) {
    await selects[i].selectOption(i < 6 ? '採用' : '保留');
  }
  const reasons = await page.$$('input[name^="reason_"]');
  if (reasons[0]) await reasons[0].fill('委員会で採用することに合意');
  await Promise.all([page.waitForURL(/#findings/), page.click('text=判断を保存する')]);
  log('指摘の判断を保存', selects.length, '件の選択欄');

  // 4. 改定案を作る
  await Promise.all([page.waitForLoadState('load'), page.click('text=採用した指摘から改定案を作る')]);
  await page.waitForTimeout(5000);
  await shot('04_drafting.png', false);
  await waitStatus(page, url, ['改定案あり'], 25);
  await page.goto(url);
  await shot('05_draft_done.png');
  await page.goto(url + '/taisho');
  await shot('06_taisho.png');

  // 5. 理事会の検討資料を作る
  await page.goto(url);
  await Promise.all([page.waitForLoadState('load'), page.click('text=理事会の検討資料を作る')]);
  await waitStatus(page, url, ['検討資料あり'], 8);
  await page.goto(url + '#board');
  await shot('07_board_before.png');
  await page.goto(url + '/board');
  await shot('08_board_paper.png');

  // 6. 理事会の判断を記録する（①理解した ②最初の1つは見送り・ほかは採用 ③確認した）
  await page.goto(url + '#board');
  const bsel = await page.$$('select[name^="b_decision_"]');
  let firstOpt = true;
  for (const s of bsel) {
    const opts = await s.$$eval('option', os => os.map(o => o.value));
    if (opts.includes('理解した')) await s.selectOption('理解した');
    else if (opts.includes('採用')) { await s.selectOption(firstOpt ? '見送り' : '採用'); firstOpt = false; }
    else if (opts.includes('確認した')) await s.selectOption('確認した');
  }
  const bnotes = await page.$$('input[name^="b_note_"]');
  if (bnotes[0]) await bnotes[0].fill('理事会で内容を確認した（質問なし）');
  await Promise.all([page.waitForURL(/#board/), page.click('text=理事会の判断を保存する')]);
  log('理事会の判断を保存', bsel.length, '議題');
  await shot('09_board_decided.png');

  // 7. 住民向け説明を作る
  await Promise.all([page.waitForLoadState('load'), page.click('text=住民向けの説明を作る')]);
  await waitStatus(page, url, ['説明文あり'], 8);
  await page.goto(url);
  await shot('10_all_done.png');
  await page.goto(url + '/explain');
  await shot('11_explain.png');

  log('完了', url);
  await browser.close();
})().catch(e => { log('失敗:', e.message); process.exit(1); });
