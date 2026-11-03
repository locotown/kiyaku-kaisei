# 仮のデモ動画の作り方

構成は2パターン。環境変数 `PATTERN` で切り替える（各スクリプトの出力も rows_a.json／rows_b.json のように分かれる）。
- `PATTERN=a`：初期版（docs/DEMO.md）。日本のマンション事情から入る
- `PATTERN=b`：何を作ったかを先に見せる（docs/demo/DEMO_B.md）。素材の割り当ては patterns/b.json

台本（docs/DEMO.md の「場面ごとの台本」の表）どおりに、図・イラスト・画面の録画をつなぎ、ナレーションを字幕（日本語＋英語）として焼き込む。
仮のナレーションは音声合成（Open JTalk、声は HTS Voice "Mei"）。BGM と効果音は audio.py で合成した自作の音。できた動画は大きいのでコミットしない。

```bash
python3 docs/demo/video/prep.py         # 撮影用の作業データ（架空のサンプルから。private/ に置く）
# サーバーを起動しておき（uv run uvicorn app.main:app --port 8000）、作業データのマンション名を反映：
#   curl -X POST -d "org=さくら台マンション管理組合（架空）" http://127.0.0.1:8000/works/20261103-200000-dm0001/org （dm0004 も）
node docs/demo/video/record.js          # 画面を場面ごとに録画（clips/）
python3 docs/demo/video/rows.py         # 台本の表を読む（rows.json）
pdftoppm -r 110 -f 1 -l 2 -png docs/demo/booklet/sakuradai_kiyaku_kakuu.pdf docs/demo/video/bkp   # 冊子の仮画像の材料
node -e "..."                           # booklet.html を booklet.png に書き出す（仮。手元の撮影に差し替える）
node docs/demo/video/subs.js            # 字幕の画像（subs/）
# 音声合成の準備（1回だけ）：apt-get install open-jtalk open-jtalk-mecab-naist-jdic hts-voice-nitech-jp-atr503-m001
#   声「Mei」は MMDAgent_Example-1.8.zip（sourceforge.net/projects/mmdagent）の Voice/mei を docs/demo/video/voice/ に展開
VOICE=mei python3 docs/demo/video/tts.py 1.1    # ナレーションを読み上げ（女性の声 Mei）。引数は話す速さ
VOICE=m001 python3 docs/demo/video/tts.py 1.1   # 男性の声（NIT ATR503 M001。apt の hts-voice-nitech-jp-atr503-m001）
python3 docs/demo/video/timing.py       # 声の長さに合わせて場面の長さを配分し直す（合計 180 秒。女性・男性の長いほうに合わせる）
VOICE=mei python3 docs/demo/video/audio.py   # ナレーション＋BGM＋効果音を混ぜる（男性の版は VOICE=m001）
ffmpeg -i docs/demo/video/audio_mix.wav -af loudnorm=I=-16:TP=-1.5:LRA=11 -ar 48000 docs/demo/video/audio_final.wav
python3 docs/demo/video/edit.py         # 組み立て → demo_kari.mp4
```

- prep.py は、点検中・改定案作成中の画面を見せるため、実際の点検の記録を時刻だけずらして「処理中」の作業を作る。本番の撮影では、実際に点検・改定案を動かして録画し、早送りする
- 撮影した素材に差し替えるときは、edit.py の VIS（場面ごとの素材）を書き換える

## 音について
- BGM：D の陽音階（レ・ミ・ソ・ラ・シ）の静かな曲。琴に近い撥弦の音（カープラス・ストロング法）とやわらかい和音。冒頭と締めは旋律を多めに、アプリの場面は控えめにした。ナレーションの間は自動で音量を下げる
- 効果音：判子を押す「トン」（施行・可決）、章の変わり目の風の音、締めの鈴のような音
- 読み上げで誤読しやすい語は tts.py の READ で読みを指定する
- 本番では、ナレーションを人の声で録音して差し替える予定（docs/DEMO.md）

- 男性の声の版は、女性の版の映像に音だけ差し替えて作る（尺は両方の声が収まるように配分してある）：`ffmpeg -i demo_kari_b.mp4 -i audio_final_b_m001.wav -map 0:v -map 1:a -c:v copy -c:a aac demo_kari_b_otoko.mp4`
