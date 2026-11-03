# 仮のデモ動画の撮影用の作業データを用意する（すべて架空のサンプルから。private/ に置くのでコミットされない）
import json, shutil, time
from pathlib import Path
W = Path(__file__).resolve().parents[3] / 'private/work'
ORG = 'さくら台マンション管理組合（架空）'
B = W / '20261103-101327-054312'
def clone(src, dst):
    if (W / dst).exists(): shutil.rmtree(W / dst)
    shutil.copytree(src, W / dst)
    return json.load(open(W / dst / 'work.json'))
def save(dst, w): (W / dst / 'work.json').write_text(json.dumps(w, ensure_ascii=False, indent=2))
now = time.time()
def relog(entries, span):
    out = []
    n = len(entries)
    for i, e in enumerate(entries):
        ts = now - span + span * i / max(n - 1, 1) - 3
        out.append({**e, 'ts': ts, 't': time.strftime('%H:%M:%S', time.localtime(ts + 9 * 3600))})
    return out
# D1：最後まで済んだ作業
w = clone(B, '20261103-200000-dm0001'); w.update(name='規約見直し（委員会案）', org=ORG); save('20261103-200000-dm0001', w)
# D2：点検中
w = clone(B, '20261103-200000-dm0002')
log = relog(w['log'][0:17], 150)
for k in ('findings', 'decisions', 'draft', 'board', 'board_decisions', 'explain', 'meeting', 'summary'): w.pop(k, None)
w.update(name='規約見直し（委員会案）', org=ORG, status='点検中', status_since=now - 150, log=log); save('20261103-200000-dm0002', w)
# D3：改定案を作成中（採点役の2回目の確認中）
w = clone(B, '20261103-200000-dm0003')
log = relog(w['log'][42:82], 620)
for k in ('draft', 'board', 'board_decisions', 'explain', 'meeting'): w.pop(k, None)
w.update(name='規約見直し（委員会案）', org=ORG, status='改定案作成中', status_since=now - 620, log=log); save('20261103-200000-dm0003', w)
# D4：理事会で〔選択〕を選ぶ前
w = clone(W / '20261103-990000-054312', '20261103-200000-dm0004')
w.update(name='規約見直し（委員会案）', org=ORG); save('20261103-200000-dm0004', w)
print('ok')
