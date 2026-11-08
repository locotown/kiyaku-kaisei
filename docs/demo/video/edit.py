# 仮のデモ動画を組み立てる（画面の録画は上の900pxに置き、下の帯は字幕に空ける）：場面ごとに 1920×1080・30fps の部品を作り、字幕などを重ねて、つなぐ
import json
import os
import subprocess
from pathlib import Path

P = os.environ.get('PATTERN', 'a')  # パターン（a：初期版、b：何を作ったかを先に見せる）
H = Path(__file__).parent
FIG = H.parent / 'figures'
OUT = os.environ.get('OUT', f'demo_kari_{P}.mp4')  # 書き出す動画の名前（v3：OUT=demo_v3_c.mp4）
V = os.environ.get('VOICE', 'mei')                  # 音声（audio_final_{P}_{V}.wav）。外で作った音声は VOICE=ext（README）
KARI = os.environ.get('KARI', '1') == '1'           # 左上の「仮編集」の印（v3 は KARI=0）
PHOTOS = H.parent / 'photos'                        # 作者が撮った写真（コミットしない）。あれば図の代わりに使う（README）
rows = json.load(open(H / f'rows_{P}.json'))
off = json.load(open(H / 'offsets.json'))
PAT = json.load(open(H / 'patterns' / f'{P}.json'))
VIS = PAT['vis']
PHOTO_OF = {int(k): v for k, v in PAT.get('photos', {}).items()}  # 場面の番号 → 写真の名前（photos/<名前>.jpg か .png）


def photo(i):
    for ext in ('.jpg', '.jpeg', '.png'):
        if i in PHOTO_OF and (PHOTOS / (PHOTO_OF[i] + ext)).exists():
            return PHOTOS / (PHOTO_OF[i] + ext)
    return None


def clip_file(name):
    return H / 'clips' / (f'{name}.mp4' if (H / 'clips' / f'{name}.mp4').exists() else f'{name}.webm')

EXTRA = {int(k): [tuple(x) for x in v] for k, v in PAT['extra'].items()}
assert len(VIS) == len(rows)
(H / f'seg_{P}').mkdir(exist_ok=True)
parts = []
for i, (r, v) in enumerate(zip(rows, VIS)):
    d = round(r['end'] - r['start'], 2)
    kind, name = v.split(':')
    inputs, chains = [], []
    if kind == 'img':
        src = H / 'booklet.png' if name == 'booklet' else FIG / f'{name}.png'
        ph = photo(i)
        fg = FIG / f'{name}_fg.png'   # 締めの画面：写真の上に重ねる文字（背景が透明。figures/render.js が作る）
        if ph and fg.exists():        # 写真を背景にして、文字を重ねる（寄らない）
            inputs += ['-loop', '1', '-t', str(d), '-i', str(ph), '-loop', '1', '-t', str(d), '-i', str(fg)]
            chains.append(f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1[ph];[ph][1:v]overlay=0:0,fps=30,setsar=1[base]")
        else:
            if ph:
                src = ph
            inputs += ['-loop', '1', '-t', str(d), '-i', str(src)]
            frames = d * 30
            # 止めて見せる（11/8：ゆっくり寄る動きが、画面全体が微妙に揺れて見えて気持ち悪い、という作者の声から。
            # 寄る動きに戻すときは ZOOM=1）。写真は縦横比を保って中央を切り抜く
            if os.environ.get('ZOOM') == '1':
                chains.append(f"[0:v]scale=2880:1620:force_original_aspect_ratio=increase,crop=2880:1620,zoompan=z='1+0.04*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=30,setsar=1[base]")
            else:
                chains.append("[0:v]scale=1920:1080:force_original_aspect_ratio=increase:flags=lanczos,crop=1920:1080,fps=30,setsar=1[base]")
    elif kind == 'montage':  # 早回し：いくつかの画面を同じ長さずつつなぐ（「名前@開始の秒」をカンマ区切り）
        parts_m = [x.split('@') for x in name.split(',')]
        each = round(d / len(parts_m), 2)
        for j, (nm, st) in enumerate(parts_m):
            inputs += ['-ss', f"{off[nm] + float(st):.2f}", '-t', str(each), '-i', str(clip_file(nm))]
            chains.append(f"[{j}:v]scale=1920:900:flags=lanczos,pad=1920:1080:0:0:color=0xf6f5f2,fps=30,tpad=stop_mode=clone:stop_duration={each},trim=duration={each},setpts=PTS-STARTPTS,setsar=1[m{j}]")
        chains.append(''.join(f'[m{j}]' for j in range(len(parts_m))) + f'concat=n={len(parts_m)}:v=1:a=0[base]')
    else:
        inputs += ['-ss', f"{off[name]:.2f}", '-t', str(d), '-i', str(clip_file(name))]
        chains.append(f"[0:v]scale=1920:900:flags=lanczos,pad=1920:1080:0:0:color=0xf6f5f2,fps=30,tpad=stop_mode=clone:stop_duration={d},trim=duration={d},setsar=1[base]")
    nbase = inputs.count('-i')
    layers = [(H / f'subs_{P}' / f'{i:02d}.png', 'full', 0, 0, 0)] + ([(H / f'subs_{P}' / 'kari.png', 'full', 0, 0, 0)] if KARI else [])
    for nm, typ, t, x, y in EXTRA.get(i, []):
        layers.append(((FIG / f'{nm}.png') if typ == 'stamp' else (H / f'subs_{P}' / f'{nm}.png'), typ, t, x, y))
    cur = 'base'
    for k, (p, typ, t, x, y) in enumerate(layers, start=nbase):
        inputs += ['-loop', '1', '-t', str(d), '-i', str(p)]
        if typ == 'stamp':  # 判子：大きめから押し付けるように縮めて現れる
            chains.append(f"[{k}:v]format=rgba,scale=w='if(lt(t,{t}+0.25),520*(1.6-2.4*max(t-{t},0)),520)':h=-1:eval=frame[s{k}]")
            chains.append(f"[{cur}][s{k}]overlay=x='{x}-(overlay_w-520)/2':y='{y}-(overlay_h-520)/2':enable='gte(t,{t})':eval=frame[l{k}]")
        else:
            chains.append(f"[{cur}][{k}:v]overlay=0:0[l{k}]")
        cur = f'l{k}'
    out = H / f'seg_{P}' / f'{i:02d}.mp4'
    cmd = ['ffmpeg', '-loglevel', 'error', '-y', *inputs, '-filter_complex', ';'.join(chains), '-map', f'[{cur}]',
           '-t', str(d), '-r', '30', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', str(out)]
    subprocess.run(cmd, check=True)
    parts.append(out)
    print(i, v, d, '秒')
(H / 'list.txt').write_text(''.join(f"file '{p}'\n" for p in parts))
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(H / 'list.txt'),
                '-i', str(H / f'audio_final_{P}_{V}.wav'), '-map', '0:v', '-map', '1:a', '-shortest', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                '-ac', '2', '-movflags', '+faststart',
                str(H / OUT)], check=True)
print('完成', H / OUT)
