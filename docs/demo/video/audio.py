# 仮のデモ動画の音：ナレーション（Open JTalk）＋ BGM（自作：琴に似た撥弦の音・五音音階）＋ 効果音（自作：判子・場面の切り替え）
# 素材集の音は使わず、すべてここで合成する（著作権の心配がない）
import json
import os
import wave
from pathlib import Path

import numpy as np

P = os.environ.get('PATTERN', 'a')  # パターン（a：初期版、b：何を作ったかを先に見せる）
H = Path(__file__).parent
SR, TOTAL = 48000, 180.0
N = int(SR * TOTAL)
rng = np.random.default_rng(7)
rows = json.load(open(H / f'rows_{P}.json'))
PAT = json.load(open(H / 'patterns' / f'{P}.json'))
V = os.environ.get('VOICE', 'mei')

def read_wav(p):
    with wave.open(str(p)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        sr = w.getframerate()
    if sr != SR:  # 線形補間で合わせる
        x = np.interp(np.arange(int(len(x) * SR / sr)) * sr / SR, np.arange(len(x)), x)
    return x

def pluck(freq, dur=2.6, bright=0.5):
    """カープラス・ストロング法で弦をはじいた音（琴に近い）。"""
    n, p = int(SR * dur), max(int(SR / freq), 2)
    buf = rng.uniform(-1, 1, p) * 0.5
    out = np.zeros(n)
    y = np.concatenate([buf, np.zeros(n + p)])
    for s in range(p, n + p, p):  # 1周期ずつまとめて計算する
        prev = y[s - p:s]
        nxt = np.append(prev[1:], prev[-1])
        y[s:s + p] = (0.5 + 0.5 * bright) * prev * 0.996 + (0.5 - 0.5 * bright) * nxt * 0.996
    out = y[p:p + n]
    out *= np.exp(-np.arange(n) / (SR * 1.1))
    return out * 0.6

def pad(freqs, dur):
    """やわらかい持続音（和音）。ゆっくり立ち上がり、ゆっくり消える。"""
    t = np.arange(int(SR * dur)) / SR
    x = sum(np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * f * 1.003 * t) for f in freqs) / (len(freqs) * 1.5)
    env = np.minimum(1, t / 2.5) * np.minimum(1, (dur - t) / 2.5)
    return x * env

def add(buf, x, at, gain=1.0):
    i = int(at * SR)
    if i >= len(buf): return
    x = x[:len(buf) - i]
    buf[i:i + len(x)] += x * gain

# --- ナレーション
voice = np.zeros(N)
FULL = H / f'voice_out_{P}_{V}' / 'full.wav'   # 外で作った音声が1本（動画の頭から通しで読んだもの）なら、そのまま 0 秒に置く（README）
if FULL.exists():
    add(voice, read_wav(FULL), 0.0, 1.0)
else:
    for i, r in enumerate(rows):
        add(voice, read_wav(H / f'voice_out_{P}_{V}' / f'{i:02d}.wav'), r['voice_at'], 1.0)

voice *= 0.85 / np.abs(voice).max()  # ナレーションを主役の音量に

# --- BGM：D の陽音階（レ・ミ・ソ・ラ・シ）。72 拍/分。場面ごとに少し変える
NOTE = {'D3': 146.83, 'E3': 164.81, 'G3': 196.0, 'A3': 220.0, 'B3': 246.94, 'D4': 293.66, 'E4': 329.63, 'G4': 392.0, 'A4': 440.0,
        'B4': 493.88, 'D5': 587.33, 'E5': 659.26}
beat = 60 / 72
bgm = np.zeros(N)
CHORDS = [(['D3', 'A3', 'E4'], 0), (['G3', 'D4', 'B4'], 1), (['B3', 'E4', 'A4'], 2), (['A3', 'D4', 'G4'], 3)]
PHRASES = [['D5', 'B4', 'A4', None, 'B4', 'A4', 'E4', None], ['G4', 'A4', 'B4', None, 'D5', 'E5', 'D5', None],
           ['E5', 'D5', 'B4', 'A4', 'B4', None, 'A4', None], ['A4', 'G4', 'E4', None, 'D4', None, None, None]]
bar = 4 * beat * 2  # 2小節で1つの和音
t, k = 0.0, 0
while t < TOTAL:
    names, _ = CHORDS[k % 4]
    add(bgm, pad([NOTE[n] for n in names], bar + 2.5), t, 0.18)
    # ① 日本のマンション・⑧締めは琴の旋律を多めに、アプリの場面は控えめに
    dense = t < PAT['dense_until'] or t > PAT['dense_after']
    for j, n in enumerate(PHRASES[k % 4]):
        if n and (dense or j % 2 == 0):
            add(bgm, pluck(NOTE[n], bright=0.35), t + j * beat, 0.22 if dense else 0.14)
    t += bar; k += 1
fade = np.ones(N); fl = int(SR * 3)
fade[:fl] = np.linspace(0, 1, fl); fade[-fl:] = np.linspace(1, 0, fl)
bgm *= fade
bgm *= 0.035 / np.sqrt((bgm ** 2).mean())  # ナレーションより十分小さく（約 -13dB）

# --- ナレーションが鳴っている間は BGM を下げる（ダッキング）
env = np.abs(voice)
win = int(SR * 0.35)
env = np.convolve(env, np.ones(win) / win, mode='same')
duck = 1 - 0.55 * np.clip(env / (env.max() * 0.15 + 1e-9), 0, 1)
duck = np.convolve(duck, np.ones(int(SR * 0.3)) / int(SR * 0.3), mode='same')
bgm *= duck

# --- 効果音
def stamp():
    """判子を押す音：低い「トン」と、紙に当たる短いノイズ。"""
    n = int(SR * 0.35); t = np.arange(n) / SR
    body = np.sin(2 * np.pi * (95 - 40 * t / 0.35) * t) * np.exp(-t / 0.05)
    noise = rng.uniform(-1, 1, n) * np.exp(-t / 0.012)
    noise = np.convolve(noise, np.ones(12) / 12, mode='same')
    return 0.9 * body + 0.5 * noise

def whoosh(dur=0.7):
    """場面の切り替え：やわらかい風の音。"""
    n = int(SR * dur); t = np.arange(n) / SR
    x = rng.uniform(-1, 1, n)
    lo = np.convolve(x, np.ones(48) / 48, mode='same')   # こもった風
    hi = np.convolve(x, np.ones(8) / 8, mode='same')     # 明るい風
    k = t / dur
    return ((1 - k) * lo + k * hi * 0.5) * np.sin(np.pi * t / dur) ** 2 * 1.6

def chime():
    a = pluck(NOTE['A4'] * 2, 3.0, 0.6) * 0.8
    b = np.concatenate([np.zeros(int(SR * .18)), pluck(NOTE['D5'] * 2, 2.82, 0.6) * 0.8])
    m = min(len(a), len(b))
    return a[:m] + b[:m]

sfx = np.zeros(N)
for i, t in PAT['sfx']['stamp']:                          # 判子（施行・可決）
    add(sfx, stamp(), rows[i]['start'] + t + 0.25, 0.7)
for i in PAT['sfx']['whoosh']:                            # 章の変わり目
    add(sfx, whoosh(), rows[i]['start'] - 0.35, 0.18)
add(sfx, chime(), rows[PAT['sfx']['chime']]['start'] + 0.2, 0.35)          # 締め

mix = voice * 1.0 + bgm + sfx
mix = np.tanh(mix * 1.1) * 0.9  # はみ出しを丸める
pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
with wave.open(str(H / f'audio_mix_{P}_{V}.wav'), 'w') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
for name, x in (('bgm', bgm), ('voice', voice), ('sfx', sfx)):
    print(name, 'ピーク', round(float(np.abs(x).max()), 2), 'RMS', round(float(np.sqrt((x ** 2).mean())), 3))
