# ナレーションを Gemini 3.8 Flash TTS で「通しで1回」読ませ、場面の変わり目の間で切り分ける（11/8 作者の声：
# 場面ごとに作ると、画面が切り替わるたびに声のニュアンスが少し変わって気持ち悪い）。
#   GVOICE=Charon python3 docs/demo/video/gemini_tts_full.py
#   → voice_gemini_full_<声>/full_raw.wav（通しの1本）と 00.wav … 22.wav（切り分けたもの）、voice_ext/ に写す
#   そのあと：ext_voice.py → timing.py → subs.js → audio.py → loudnorm → edit.py（README）
# 切り分け方：無音の区間を探し、文字数の割合から見込んだ場面の境目のいちばん近い無音を、順番を崩さずに選ぶ
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault('ONLY', '-1')          # gemini_tts の場面ごとの作成は動かさない（say だけ借りる）
import gemini_tts as G  # noqa: E402

H = Path(__file__).parent
VOICE = G.VOICE
OUT = H / f'voice_gemini_full_{VOICE}'
OUT.mkdir(exist_ok=True)
rows = G.rows
G.STYLE = os.environ.get('GSTYLE', '落ち着いた、はっきりした日本語のナレーション。ドキュメンタリーのように、聞き取りやすく、少し速めに。'
                                   '全体を同じ調子で通して読む。段落の変わり目では、毎回1.2秒ほどはっきり間をあける')
text = '\n\n'.join(r['jp'] for r in rows)
raw = OUT / 'full_raw.wav'
if not raw.exists() or os.environ.get('REDO'):
    raw.write_bytes(G.say(text))
dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(raw)],
                           capture_output=True, text=True).stdout)
print('通しの長さ', round(dur, 1), '秒')

# 無音の区間（-38dB 以下が 0.35 秒以上）
det = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(raw), '-af', 'silencedetect=noise=-38dB:d=0.35', '-f', 'null', '-'],
                     capture_output=True, text=True).stderr
starts = [float(x) for x in re.findall(r'silence_start: ([\d.]+)', det)]
ends = [float(x) for x in re.findall(r'silence_end: ([\d.]+)', det)]
gaps = [(s, e) for s, e in zip(starts, ends) if s > 0.2 and e < dur - 0.2]
print('間の数', len(gaps))
n = len(rows)
if len(gaps) < n - 1:
    sys.exit('間が足りず、切り分けられません。GSTYLE で間を長くするよう指示して REDO=1 で作り直してください')

# 文字数の割合から境目を見込み、近い間を順番に選ぶ（動的計画法：見込みとの差の合計を最小に、間の長さを少し優遇）
chars = [len(re.sub(r'[\s、。「」（）]', '', r['jp'])) for r in rows]
total = sum(chars)
expect = []
acc = 0
for c in chars[:-1]:
    acc += c
    expect.append(dur * acc / total)
INF = float('inf')
G_ = len(gaps)
cost = [[INF] * G_ for _ in range(n - 1)]
back = [[-1] * G_ for _ in range(n - 1)]
for k in range(n - 1):
    for j in range(G_):
        mid = (gaps[j][0] + gaps[j][1]) / 2
        c = abs(mid - expect[k]) - 0.8 * (gaps[j][1] - gaps[j][0])
        if k == 0:
            cost[k][j] = c
        else:
            best = min(((cost[k - 1][i], i) for i in range(j)), default=(INF, -1))
            if best[0] < INF:
                cost[k][j], back[k][j] = best[0] + c, best[1]
j = min(range(G_), key=lambda x: cost[n - 2][x])
pick = []
for k in range(n - 2, -1, -1):
    pick.append(j)
    j = back[k][j]
pick.reverse()
cuts = [0.0] + [(gaps[j][0] + gaps[j][1]) / 2 for j in pick] + [dur]
for i in range(n):
    a, b = cuts[i], cuts[i + 1]
    dst = OUT / f'{i:02d}.wav'
    # 前後の無音を削る（場面の頭と終わりの間は timing.py が決める）
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', str(raw), '-ss', f'{a:.3f}', '-to', f'{b:.3f}',
                    '-af', 'silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,'
                           'silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08,areverse',
                    str(dst)], check=True)
    print(f'{i:02d}', f'{a:6.2f}–{b:6.2f}', rows[i]['jp'][:18])
ext = H / 'voice_ext'
if ext.exists():
    shutil.rmtree(ext)
ext.mkdir()
for f in OUT.glob('[0-9][0-9].wav'):
    shutil.copy(f, ext / f.name)
json.dump({'voice': VOICE, 'cuts': cuts, 'duration': dur}, open(OUT / 'cuts.json', 'w'), indent=1)
print('voice_ext/ に写しました。続けて ext_voice.py から組み直してください')
