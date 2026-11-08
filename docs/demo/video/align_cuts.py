# 通しのナレーションの場面の境目を、文字起こし（faster-whisper）の単語の時刻で決める（11/8）
#   無音の長さだけでは、段落の間と文の途中の間が区別しきれず、後半の場面がずれた
#   uv run --with faster-whisper --with numpy python -I docs/demo/video/align_cuts.py
#   → voice_gemini_full_<声>/bounds.json（場面の境目の秒）。gemini_tts_full.py があれば使う
# 境目の前後の文字が読まれた時刻を、期待する文と文字起こしの文字の対応（difflib）で求め、その間にある一番長い無音の真ん中で切る
import difflib
import json
import os
import re
import subprocess
from pathlib import Path

H = Path(__file__).parent
VOICE = os.environ.get('GVOICE', 'Charon')
OUT = H / f'voice_gemini_full_{VOICE}'
raw = OUT / 'full_raw.wav'
rows = json.load(open(H / f"rows_{os.environ.get('PATTERN', 'c')}.json"))
READ = {'約1,600万人': '約千六百万人'}       # gemini_tts_full.py と同じ読み替え


def norm(t: str) -> str:
    for a, b in READ.items():
        t = t.replace(a, b)
    return re.sub(r'[\s、。「」（）・，,.！？!?：:]', '', t)


wf = OUT / 'words.json'
if not wf.exists() or os.environ.get('REDO'):
    import numpy as np
    from faster_whisper import WhisperModel
    pcm = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', str(raw), '-f', 's16le', '-ac', '1', '-ar', '16000', '-'],
                         capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0    # ファイルを直接渡すと PyAV の版の違いで落ちる
    m = WhisperModel(os.environ.get('WMODEL', 'small'), device='cpu', compute_type='int8')
    segs, _ = m.transcribe(audio, language='ja', word_timestamps=True, vad_filter=False, beam_size=5)
    wf.write_text(json.dumps([{'w': w.word, 's': w.start, 'e': w.end} for s in segs for w in s.words],
                             ensure_ascii=False), encoding='utf-8')
words = json.loads(wf.read_text(encoding='utf-8'))

exp = [norm(r['jp']) for r in rows]
E = ''.join(exp)
A, at = '', []
for w in words:
    t = norm(w['w'])
    for k, ch in enumerate(t):
        A += ch
        at.append(w['s'] + (w['e'] - w['s']) * k / max(1, len(t)))
sm = difflib.SequenceMatcher(None, E, A, autojunk=False)
pos = {b.a + k: b.b + k for b in sm.get_matching_blocks() for k in range(b.size)}
det = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(raw), '-af', 'silencedetect=noise=-38dB:d=0.2', '-f', 'null', '-'],
                     capture_output=True, text=True).stderr
gaps = list(zip([float(x) for x in re.findall(r'silence_start: ([\d.]+)', det)],
                [float(x) for x in re.findall(r'silence_end: ([\d.]+)', det)]))
bounds, acc = [], 0
for i, e in enumerate(exp[:-1]):
    acc += len(e)
    p = max(k for k in range(acc) if k in pos)                # 境目の直前で、対応がとれた文字
    q = min(k for k in range(acc, len(E)) if k in pos)        # 境目の直後で、対応がとれた文字
    t0, t1 = at[pos[p]], at[pos[q]]
    cand = [g for g in gaps if g[1] >= t0 - 0.3 and g[0] <= t1 + 0.3]
    g = max(cand, key=lambda g: g[1] - g[0]) if cand else None
    bounds.append((g[0] + g[1]) / 2 if g else (t0 + t1) / 2)
    print(f'{i:02d}|{i + 1:02d} {bounds[-1]:7.2f}', '無音' if g else '（無音なし）', E[p - 4:p + 1], '/', E[q:q + 5])
(OUT / 'bounds.json').write_text(json.dumps(bounds), encoding='utf-8')
print('文字の一致', round(sm.ratio(), 3), '→', OUT / 'bounds.json')
