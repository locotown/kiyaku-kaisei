# デモ動画 v3（11/8）の撮影用の作業を用意する。すべて架空のサンプル「Word の規約集（架空）」から、本物の AI で作った作業の写し。
# 撮影用の保存先（環境変数 KIYAKU_DATA_DIR。リポジトリの外）に置くので、コミットされない。
#
# 作り方（実際に行った手順。画面のフォームと同じ送信で進めた）：
#   1. 撮影用のサーバー：KIYAKU_KB_OFF=1 KIYAKU_DATA_DIR=<撮影用> uv run uvicorn app.main:app --port 8800
#   2. サンプル（sample=docx）で作業を作る → 作業の名前・管理組合の名前を「さくら台マンション管理組合（架空）」に
#   3. 点検 → 推奨を3件「改定案に入れる」→ 改定案 → 理事会の検討資料 → 〔選択〕を選んで対象の条だけ作り直す
#      → 住民向けの説明 → 総会の結果（可決）→ 最新の規約
#   段階が終わるたびに、作業のフォルダを別の ID（20261108-110038-v3s…）で写した。処理中の作業の work.json は、5秒ごとに v3_snap/ に写した
#
# このスクリプトは、処理中（点検中・改定案作成中）の画面を録るため、写しておいた処理中の work.json の時刻を「いま」にずらした作業を作り、
# 撮影する作業の ID を ids_v3.json に書く（record.js が読む）。録画の直前に動かす（経過時間が「いま」から数えられるため）。
import json
import os
import shutil
import sys
import time
from pathlib import Path

H = Path(__file__).parent
DATA = Path(os.environ.get('KIYAKU_DATA_DIR', ''))
if not DATA.name:
    sys.exit('KIYAKU_DATA_DIR（撮影用の保存先）を指定してください')
WORK, SNAP = DATA / 'work', DATA / 'v3_snap'
SRC = '20261108-110038-9e6e0c'   # 本物の AI で最初から作った作業
IDS = {
    'reviewed': '20261108-110038-v3s1rv',   # 点検が終わった直後（まだ判断していない）
    'decided': '20261108-110038-v3s2dc',    # 推奨を3件採用した
    'drafted': '20261108-110038-v3s3df',    # 改定案ができた
    'board': '20261108-110038-v3s4bd',      # 理事会の検討資料ができた（〔選択〕はまだ選んでいない）
    'redrafted': '20261108-110038-v3s5rd',  # 〔選択〕を選び、対象の条だけ作り直した
    'explained': '20261108-110038-v3s6ex',  # 住民向けの説明ができた
    'final': '20261108-110038-v3s7mt',      # 総会で可決し、最新の規約ができた
    'review_busy': '20261108-110038-v3b1rv',
    'draft_busy': '20261108-110038-v3b2df',
}
now = time.time()


def busy(key, snap, src_stage, span):
    """写しておいた処理中の work.json（snap）から、いま処理している最中に見える作業を作る。span 秒前に始まったことにする。"""
    w = json.load(open(SNAP / snap))
    since = w['status_since']
    cur = [e for e in w['log'] if e.get('ts', 0) >= since - 1]
    old = [e for e in w['log'] if e.get('ts', 0) < since - 1]
    shift = (now - 3) - cur[-1]['ts']        # 最後の記録を3秒前に
    k = span / max(now - 3 - (since + shift), 1)   # 実際の経過を span 秒に縮める（記録の間隔の比は保つ）
    def move(e):
        ts = (now - 3) - (cur[-1]['ts'] - e['ts']) * k
        return {**e, 'ts': ts, 't': time.strftime('%H:%M:%S', time.gmtime(ts + 9 * 3600))}
    w['log'] = [{**e, 'ts': e['ts'] - (since - (now - span)) - 60} for e in old] + [move(e) for e in cur]
    w.update(status_since=now - span, demo_busy=True)
    dst = WORK / IDS[key]
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(WORK / IDS[src_stage], dst)
    (dst / 'work.json').write_text(json.dumps(w, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    pick = json.load(open(H / 'ids_v3_snap.json')) if (H / 'ids_v3_snap.json').exists() else {}
    if pick.get('review'):
        busy('review_busy', pick['review'], 'reviewed', pick.get('review_span', 120))
    if pick.get('draft'):
        busy('draft_busy', pick['draft'], 'decided', pick.get('draft_span', 300))
    (H / 'ids_v3.json').write_text(json.dumps(IDS, ensure_ascii=False, indent=1))
    print('ok', {k: (WORK / v).exists() for k, v in IDS.items()})
