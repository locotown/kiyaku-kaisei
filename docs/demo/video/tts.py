# 台本のナレーションを Open JTalk（声：Mei）で読み上げ、場面ごとの wav にする
import json
import os
import subprocess
import sys
from pathlib import Path

P = os.environ.get('PATTERN', 'a')  # パターン（a：初期版、b：何を作ったかを先に見せる）
VOICES = {'mei': 'voice/MMDAgent_Example-1.8/Voice/mei/mei_normal.htsvoice', 'm001': '/usr/share/hts-voice/nitech-jp-atr503-m001/nitech_jp_atr503_m001.htsvoice'}
V = os.environ.get('VOICE', 'mei')  # 声（mei：女性、m001：男性）
H = Path(__file__).parent
RATE = float(sys.argv[1]) if len(sys.argv) > 1 else 1.1
READ = [  # 読み上げで誤読しやすい語の読み
    ('ととのう規約', 'ととのうきやく'), ('二段構え', 'にだんがまえ'), ('山本', 'やまもと'),
    ('1,600万人', '千六百万人'), ('10人に1人', '十人に一人'), ('4割', 'よんわり'), ('2026年4月', '二千二十六年四月'),
    ('何千万円', 'なんぜんまんえん'), ('Word', 'ワード'), ('Claude', 'クロード'), ('Web', 'ウェブ'), ('AI', 'エーアイ'),
    ('11の基準', 'じゅういちの基準'), ('3種類', 'さんしゅるい'), ('約半数', 'やくはんすう'), ('新旧対照表', 'しんきゅうたいしょうひょう'),
    ('附則', 'ふそく'), ('規約', 'きやく'), ('細則', 'さいそく'),
    ('3本', 'さんぼん'), ('8つ', 'やっつ'), ('採点役', 'さいてんやく'), ('4月', 'しがつ'),
]
READ.insert(0, ('Claude Code', 'クロード コード'))  # 「Claude」より先に置き換える
rows = json.load(open(H / f'rows_{P}.json'))
(H / f'voice_out_{P}_{V}').mkdir(exist_ok=True)
out = []
for i, r in enumerate(rows):
    t = r['jp']
    for a, b in READ:
        t = t.replace(a, b)
    wav = H / f'voice_out_{P}_{V}' / f'{i:02d}.wav'
    subprocess.run(['open_jtalk', '-x', '/var/lib/mecab/dic/open-jtalk/naist-jdic', '-m', str(H / VOICES[V]) if not VOICES[V].startswith('/') else VOICES[V], '-r', str(RATE), '-fm', '0', '-a', '0.55',
                    '-ow', str(wav)], input=t.encode(), check=True)
    d = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(wav)],
                             capture_output=True, text=True).stdout)
    out.append({'i': i, 'slot': r['end'] - r['start'], 'voice': round(d, 2)})
json.dump(out, open(H / f'voice_{P}_{V}.json', 'w'), indent=1)
tot = sum(x['voice'] for x in out)
for x in out:
    flag = '  ← はみ出す' if x['voice'] + 0.4 > x['slot'] else ''
    print(f"{x['i']:2d} 枠 {x['slot']:3d}秒 声 {x['voice']:5.2f}秒{flag}")
print('声の合計', round(tot, 1), '秒')
