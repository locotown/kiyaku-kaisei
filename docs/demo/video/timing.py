# 読み上げの長さに合わせて場面の長さを配分し直す（合計は 180 秒）。声が収まらない場面を延ばし、余る場面を詰める
import json
import os
from pathlib import Path

P = os.environ.get('PATTERN', 'a')  # パターン（a：初期版、b：何を作ったかを先に見せる）
H = Path(__file__).parent
rows = json.load(open(H / f'rows_{P}.json'))
# 女性・男性の両方の声が収まるよう、長いほうに合わせる（映像は1回だけ組み立て、音だけ差し替える）
voice = {}
ONLY = os.environ.get('VOICE')  # 声を1つに絞る（例：VOICE=mei。外で作った音声は VOICE=ext）。省くと、ある声すべての長いほう
for vf in (H.glob(f'voice_{P}_{ONLY}.json') if ONLY else H.glob(f'voice_{P}_*.json')):
    for v in json.load(open(vf)):
        voice[v['i']] = max(voice.get(v['i'], 0), v['voice'])
TOTAL, LEAD, TAIL = 180.0, 0.3, 0.6
need = [voice[i] + LEAD + TAIL for i in range(len(rows))]
slot = [r['end'] - r['start'] for r in rows]
lo, hi = 0.3, 1.5
for _ in range(60):  # d_i = max(need_i, slot_i * k) の k を二分法で決める
    k = (lo + hi) / 2
    s = sum(max(n, sl * k) for n, sl in zip(need, slot))
    lo, hi = (k, hi) if s < TOTAL else (lo, k)
d = [max(n, sl * k) for n, sl in zip(need, slot)]
d = [round(x * TOTAL / sum(d), 2) for x in d]
t = 0.0
for r, x in zip(rows, d):
    r['script_start'], r['script_end'] = r['start'], r['end']
    r['start'], r['end'] = round(t, 2), round(t + x, 2)
    r['voice_at'] = round(t + LEAD, 2)
    t += x
rows[-1]['end'] = TOTAL
json.dump(rows, open(H / f'rows_{P}.json', 'w'), ensure_ascii=False, indent=1)
for r in rows:
    print(f"{r['script_start']:>4}→{r['start']:6.1f}秒  長さ {r['end'] - r['start']:5.1f}（台本 {r['script_end'] - r['script_start']}）")
