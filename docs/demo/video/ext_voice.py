# 外で作ったナレーション（自分の声・Gemini などの音声合成）を、動画の組み立てに使える形にする。
#   置き場所：docs/demo/video/voice_ext/（コミットしない）
#   場面ごと：00.wav 01.wav … 22.wav（narration_c.txt の番号。mp3・m4a も可）。足りない番号は Mei の声で埋める
#   1本だけ：full.wav（動画の頭から通しで読んだもの。場面の長さは今のまま）
# 出力：voice_out_{P}_ext/（48kHz・モノラル）と voice_{P}_ext.json（場面ごとの長さ。timing.py が読む）
import json
import os
import shutil
import subprocess
from pathlib import Path

P = os.environ.get('PATTERN', 'c')
H = Path(__file__).parent
SRC, OUT = H / 'voice_ext', H / f'voice_out_{P}_ext'
rows = json.load(open(H / f'rows_{P}.json'))
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir()


def conv(src, dst):
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-i', str(src), '-ac', '1', '-ar', '48000', '-sample_fmt', 's16', str(dst)], check=True)
    return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(dst)],
                                capture_output=True, text=True).stdout)


full = [f for f in SRC.glob('full.*')]
if full:
    d = conv(full[0], OUT / 'full.wav')
    print('1本の音声', round(d, 1), '秒（180秒を超えた分は切れます）')
out = []
for i in range(len(rows)):
    src = next((f for ext in ('.wav', '.mp3', '.m4a', '.aac', '.ogg', '.flac') for f in [SRC / f'{i:02d}{ext}'] if f.exists()), None)
    if src is None:  # ない場面は Mei の声（tts.py で作ったもの）
        src = H / f'voice_out_{P}_mei' / f'{i:02d}.wav'
        print(f'{i:02d}：外の音声がないので Mei の声を使います')
    d = conv(src, OUT / f'{i:02d}.wav')
    out.append({'i': i, 'slot': rows[i]['end'] - rows[i]['start'], 'voice': round(d, 2)})
json.dump(out, open(H / f'voice_{P}_ext.json', 'w'), indent=1)
print('場面ごとの声の合計', round(sum(x['voice'] for x in out), 1), '秒')
