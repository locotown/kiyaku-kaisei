# 仮のデモ動画を組み立てる：場面ごとに 1920×1080・30fps の部品を作り、字幕などを重ねて、つなぐ
import json, subprocess
from pathlib import Path
H = Path(__file__).parent
FIG = H.parent / 'figures'
rows = json.load(open(H / 'rows.json'))
off = json.load(open(H / 'offsets.json'))
VIS = ['img:05_danchi', 'img:06_soukai', 'img:01_japan', 'img:07_law', 'img:02_kiyaku', 'img:08_shuuzen', 'img:booklet',
       'clip:c1_upload', 'clip:c2_review_busy', 'clip:c3_findings', 'clip:c4_basis_bulk', 'clip:c5_draft_busy', 'clip:c6_quality',
       'clip:c7_taisho', 'clip:c8_questions', 'clip:c9_board_done', 'clip:c10_explain', 'clip:c11_meeting', 'clip:c12_final',
       'img:03_architecture', 'img:04_eval', 'img:09_end']
EXTRA = {3: [('07s_stamp_shikou', 'stamp', 1.4, 1300, 470)], 6: [('booklet', 'badge', 0, 0, 0)], 8: [('ff_review', 'badge', 0, 0, 0)],
         11: [('ff_draft', 'badge', 0, 0, 0)], 17: [('07s_stamp_kaketsu', 'stamp', 2.5, 1330, 300)]}
assert len(VIS) == len(rows)
(H / 'seg').mkdir(exist_ok=True)
parts = []
for i, (r, v) in enumerate(zip(rows, VIS)):
    d = round(r['end'] - r['start'], 2)
    kind, name = v.split(':')
    inputs, chains = [], []
    if kind == 'img':
        src = H / 'booklet.png' if name == 'booklet' else FIG / f'{name}.png'
        inputs += ['-loop', '1', '-t', str(d), '-i', str(src)]
        frames = d * 30
        # ゆっくり寄る（拡大してから zoompan で揺れを抑える）
        chains.append(f"[0:v]scale=2880:1620,zoompan=z='1+0.04*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=30,setsar=1[base]")
    else:
        inputs += ['-ss', f"{off[name]:.2f}", '-t', str(d), '-i', str(H / 'clips' / f'{name}.webm')]
        chains.append(f"[0:v]scale=1920:1080:flags=lanczos,fps=30,tpad=stop_mode=clone:stop_duration={d},trim=duration={d},setsar=1[base]")
    layers = [(H / 'subs' / f'{i:02d}.png', 'full', 0, 0, 0), (H / 'subs' / 'kari.png', 'full', 0, 0, 0)]
    for nm, typ, t, x, y in EXTRA.get(i, []):
        layers.append(((FIG / f'{nm}.png') if typ == 'stamp' else (H / 'subs' / f'{nm}.png'), typ, t, x, y))
    cur = 'base'
    for k, (p, typ, t, x, y) in enumerate(layers, start=1):
        inputs += ['-loop', '1', '-t', str(d), '-i', str(p)]
        if typ == 'stamp':  # 判子：大きめから押し付けるように縮めて現れる
            chains.append(f"[{k}:v]format=rgba,scale=w='if(lt(t,{t}+0.25),520*(1.6-2.4*max(t-{t},0)),520)':h=-1:eval=frame[s{k}]")
            chains.append(f"[{cur}][s{k}]overlay=x='{x}-(overlay_w-520)/2':y='{y}-(overlay_h-520)/2':enable='gte(t,{t})':eval=frame[l{k}]")
        else:
            chains.append(f"[{cur}][{k}:v]overlay=0:0[l{k}]")
        cur = f'l{k}'
    out = H / 'seg' / f'{i:02d}.mp4'
    cmd = ['ffmpeg', '-loglevel', 'error', '-y', *inputs, '-filter_complex', ';'.join(chains), '-map', f'[{cur}]',
           '-t', str(d), '-r', '30', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', str(out)]
    subprocess.run(cmd, check=True)
    parts.append(out)
    print(i, v, d, '秒')
(H / 'list.txt').write_text(''.join(f"file '{p}'\n" for p in parts))
subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', str(H / 'list.txt'),
                '-i', str(H / 'audio_final.wav'), '-map', '0:v', '-map', '1:a', '-shortest', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                '-ac', '2', '-movflags', '+faststart',
                str(H / 'demo_kari.mp4')], check=True)
print('完成', H / 'demo_kari.mp4')
