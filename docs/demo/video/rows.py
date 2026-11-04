# docs/DEMO.md の台本の表から、場面ごとの（開始秒, 画面, ナレーション, 英語）を取り出す
import re, json, os
from pathlib import Path
H = Path(__file__).parent
P = os.environ.get('PATTERN', 'a')
PAT = json.load(open(H / 'patterns' / f'{P}.json'))
s = open(H.parents[2] / PAT['script'], encoding='utf-8').read()
body = s.split('## 場面ごとの台本')[1].split('## 撮影の準備')[0]
rows = []
for line in body.splitlines():
    m = re.match(r'^\| (\d):(\d\d) \| (.*?) \| (.*?) \| (.*?) \|$', line)
    if m:
        rows.append({'start': int(m[1]) * 60 + int(m[2]), 'visual': m[3], 'jp': m[4], 'en': m[5]})
for i, r in enumerate(rows):
    r['end'] = rows[i + 1]['start'] if i + 1 < len(rows) else 180
json.dump(rows, open(H / f'rows_{P}.json', 'w'), ensure_ascii=False, indent=1)
print(len(rows), [(r['start'], r['end']) for r in rows])
