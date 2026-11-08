# ナレーションを Gemini 3.8 Flash TTS で作る（11/8 作者の依頼。合成音声 Mei の代わりに試す）
#   キーは、Claude Code の環境の Network secrets（host: generativelanguage.googleapis.com、header: x-goog-api-key）に
#   作者が入れる。通信のときに自動で付くので、このスクリプトにもリポジトリにもキーは書かない
#   手元で動かすときは、環境変数 GEMINI_API_KEY を使う
#
#   GVOICE=Kore python3 docs/demo/video/gemini_tts.py          # 全場面 → voice_ext/00.wav … 22.wav
#   GVOICE=Kore ONLY=3 python3 docs/demo/video/gemini_tts.py   # 1場面だけ試す
#   出力のあと：ext_voice.py → timing.py → subs.js → audio.py → loudnorm → edit.py（README の「自分の声・別の音声合成に差し替える」）
import base64
import json
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path

P = os.environ.get('PATTERN', 'c')
H = Path(__file__).parent
VOICE = os.environ.get('GVOICE', 'Kore')
MODEL = os.environ.get('GMODEL', 'gemini-3.8-flash-tts')
STYLE = os.environ.get('GSTYLE', '落ち着いた、はっきりした日本語のナレーション。ドキュメンタリーのように、聞き取りやすく、少し速めに')
OUT = H / f'voice_gemini_{VOICE}'   # 声ごとに残す（voice_ext/ には最後に写す）
URL = 'https://generativelanguage.googleapis.com/v1beta/interactions'
rows = json.load(open(H / f'rows_{P}.json'))
only = os.environ.get('ONLY')
OUT.mkdir(exist_ok=True)


def say(text: str) -> bytes:
    body = {"model": MODEL,
            "input": [{"type": "user_input", "content": [{"type": "text", "text": text,
                                                          "annotations": [{"type": "speech_metadata", "style": STYLE}]}]}],
            "response_format": {"type": "audio", "mime_type": "audio/wav"},
            "generation_config": {"speech_config": [{"voice": VOICE}]}}
    headers = {"Content-Type": "application/json"}
    if os.environ.get('GEMINI_API_KEY'):
        headers["x-goog-api-key"] = os.environ['GEMINI_API_KEY']
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=headers, method='POST')
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
            audio = [c for s in data.get('steps', []) if s.get('type') == 'model_output'
                     for c in s.get('content', []) if c.get('type') == 'audio']
            if not audio:
                raise RuntimeError('音声が返りませんでした：' + json.dumps(data, ensure_ascii=False)[:300])
            return base64.b64decode(audio[-1]['data'])
        except urllib.error.HTTPError as e:
            msg = e.read().decode('utf-8', 'ignore')[:400]
            if e.code in (429, 500, 503) and attempt < 3:
                time.sleep(5 * (attempt + 1))
                continue
            sys.exit(f'Gemini API のエラー {e.code}：{msg}')
    raise RuntimeError('くり返し失敗しました')


for i, r in enumerate(rows):
    if only is not None and i != int(only):
        continue
    wav = say(r['jp'])
    (OUT / f'{i:02d}.wav').write_bytes(wav)
    print(f'{i:02d}', VOICE, len(wav), 'bytes', r['jp'][:20])
if only is None:
    ext = H / 'voice_ext'
    ext.mkdir(exist_ok=True)
    for f in OUT.glob('*.wav'):
        shutil.copy(f, ext / f.name)
    print('voice_ext/ に写しました。続けて ext_voice.py から組み直してください')
