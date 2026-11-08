# 場面ごとのナレーションの文と長さの一覧（narration_{P}.txt）を作る。自分の声や別の音声合成で読むときの台本（README）
# timing.py のあとに動かす（場面の長さは、Mei の声に合わせて配分したもの）
import json
import os
from pathlib import Path

P = os.environ.get('PATTERN', 'c')
H = Path(__file__).parent
rows = json.load(open(H / f'rows_{P}.json'))
mei = {v['i']: v['voice'] for v in json.load(open(H / f'voice_{P}_mei.json'))} if (H / f'voice_{P}_mei.json').exists() else {}
fmt = lambda t: f"{int(t // 60)}:{t % 60:04.1f}"
lines = [f'# ナレーションの台本（パターン{P.upper()}・{len(rows)}場面・合計 180 秒）',
         '# 番号＝外の音声のファイル名（00.wav など）。「話す長さ」は、場面の中で声に使える長さ（前に0.3秒・後に0.6秒の間を残す）。',
         '# Mei の声の長さを目安に、1秒に6〜7字で読む。長く読むと、組み直したときに場面が延び、ほかの場面が詰まる（合計は180秒のまま）。',
         '# 1本で読むときは、動画（demo_v3_c.mp4）を流しながら「開始」の時刻に合わせて読み、full.wav として置く。', '']
for i, r in enumerate(rows):
    d = r['end'] - r['start']
    lines.append(f"[{i:02d}] {fmt(r['start'])}–{fmt(r['end'])}　場面の長さ {d:.1f}秒　話す長さ {max(d - 0.9, 0):.1f}秒まで"
                 + (f"　（Mei {mei[i]:.1f}秒）" if i in mei else '') + f"　{len(r['jp'])}字")
    lines.append(f"　画面：{r['visual']}")
    lines.append(f"　{r['jp']}")
    lines.append('')
(H / f'narration_{P}.txt').write_text('\n'.join(lines), encoding='utf-8')
print('書き出し', H / f'narration_{P}.txt')
