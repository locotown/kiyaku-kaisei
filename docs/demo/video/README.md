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

## 現在の版（11/3 夜）
- ver2：パターンB と C（女性の声 Mei を採用）。保留中。ファイルは demo_ver2_b.mp4・demo_ver2_c.mp4（コミットしない）

## 11/4 第3案のデザインで録り直した版
- demo_ver2_b_design3.mp4・demo_ver2_c_design3.mp4：ナレーション・図・尺は ver2 のまま、アプリの場面だけ新しいデザインで録り直した（コミットしない）
- 画面の録画は 1280×600 で撮り、動画では上の900pxに置いて、下の帯（地の色）を字幕に空ける。下に固定した帯（次の一手）と字幕が重ならない
- 印刷用の資料（新旧対照表・検討資料・住民向けの説明・最新の規約）も新しい見た目で映っている

## 11/8 v3（パターンC・合成音声の完成版）：demo_v3_c.mp4
アプリの場面（③ 0:38–2:05）を今の画面で撮り直した版。ナレーションは Mei（話す速さ 1.15）。動画・音声・画像はコミットしない。

### 撮影用の作業（本物の AI で作った）
- 撮影用のサーバーは、保存先を分けて起動する（トップ画面の「これまでの作業」にテスト用の作業が映らない）。v3 の撮影用の作業は `private/video_data/` に置いた（コミットしない）。
  `KIYAKU_KB_OFF=1 KIYAKU_DATA_DIR=private/video_data uv run uvicorn app.main:app --port 8800`
- サンプル「Word の規約集（架空）」から、名前・管理組合を「さくら台マンション管理組合（架空）」にして、点検 → 推奨を採用 → 改定案 → 理事会の検討資料 → 〔選択〕を選んで対象の条だけ作り直し → 住民向けの説明 → 総会（可決）→ 最新の規約まで、画面と同じフォームの送信で進めた。段階ごとに作業のフォルダを写した（どの ID がどの段階かは prep_v3.py）
- 点検中・改定案作成中の画面は、処理中に5秒ごとに写した work.json から、prep_v3.py が時刻を「いま」にずらして作る（早送りの印に、実際にかかった時間を出す：点検 2分41秒・改定案 7分01秒）

### 録画（record.js）
- 1920×900 の画面に、ページを CSS の zoom 1.5 倍で表示して録る（見え方は 1280×600 と同じで、文字が1.5倍の画素でくっきりする）。Chrome の screencast の JPEG を ffmpeg で 30fps の mp4（clips/*.mp4）にする。edit.py はそのまま上の900pxに置く
- `node docs/demo/video/record.js c3_findings c8_questions` のように、場面を選んで録り直せる（offsets.json の該当の場面だけ書き換わる）

### 組み立て（全部）
```bash
S=private/video_data   # 撮影用の保存先（.gitignore 済み。v3 の作業・処理中の写し v3_snap/ を置いた）
KIYAKU_DATA_DIR=$S python3 docs/demo/video/prep_v3.py      # 処理中の画面の作業を作り、ids_v3.json を書く
BASE=http://127.0.0.1:8800 node docs/demo/video/record.js  # 画面の録画（clips/*.mp4）
export PATTERN=c
python3 docs/demo/video/rows.py                 # 台本（docs/demo/DEMO_C.md）の表を読む
VOICE=mei python3 docs/demo/video/tts.py 1.15   # Mei で読み上げ
VOICE=mei python3 docs/demo/video/timing.py     # 声の長さに合わせて場面の長さを配分（合計180秒）
python3 docs/demo/video/narration.py            # narration_c.txt（場面ごとの文と長さ）
node docs/demo/video/subs.js                    # 字幕・早送りの印
VOICE=mei python3 docs/demo/video/audio.py      # ナレーション＋BGM＋効果音
ffmpeg -y -i docs/demo/video/audio_mix_c_mei.wav -af loudnorm=I=-16:TP=-1.5:LRA=11 -ar 48000 docs/demo/video/audio_final_c_mei.wav
OUT=demo_v3_c.mp4 KARI=0 VOICE=mei python3 docs/demo/video/edit.py
```

### 写真に差し替える（①の冒頭・②の団地・⑥の締め）
作者が撮ったマンションの写真を `docs/demo/photos/` に置く（このフォルダは .gitignore 済みで、公開リポジトリに入らない）。名前で場面が決まる（patterns/c.json の "photos"）：
| ファイル | 場面 | 今の絵 |
| --- | --- | --- |
| `open.jpg` | ① 0:00 冒頭（掲示板のお知らせの場面） | 10_keijiban.png |
| `danchi.jpg` | ② 0:25「そこで山本さんが使ったのが…」 | 05_danchi.png |
| `end.jpg` | ⑥ 締めの画面の背景（文字・URL・注意書きは上に重ねる） | 09_end.png の背景 |

`.png` でもよい。横長（16:9）の写真がよい（違う比率は中央を切り抜く）。置いたら、映像だけ組み直す（1行）：
```bash
PATTERN=c OUT=demo_v3_c_photo.mp4 KARI=0 VOICE=mei python3 docs/demo/video/edit.py
```
- 写真を外すと、元の絵に戻る。⑥の文字は figures/09_end_fg.png（`node docs/demo/figures/render.js 09_end` で作り直す）
- 写真に、マンション名・表札・部屋番号・人の顔・車のナンバーが写っていないか確かめる。冒頭の掲示板の絵には「登場する人物・マンションは架空です」の注記があるが、open.jpg に差し替えると消える（締めの画面の小さい文字には残る）

### 自分の声・別の音声合成に差し替える
1. `docs/demo/video/narration_c.txt` を見て読む（場面の番号・開始の時刻・場面の長さ・話せる長さ・文）。1秒に6〜7字が目安
2. 音声を `docs/demo/video/voice_ext/` に置く（.gitignore 済み）。次のどちらか：
   - 場面ごと：`00.wav` … `22.wav`（mp3・m4a も可）。ない番号は Mei の声で埋める。場面の長さは、新しい声に合わせて配分し直す
   - 1本：`full.wav`（demo_v3_c.mp4 を流しながら、字幕の出るところで読む。場面の長さは今のまま）
3. 組み直す：
```bash
export PATTERN=c
python3 docs/demo/video/ext_voice.py                    # voice_out_c_ext/ と voice_c_ext.json
VOICE=ext python3 docs/demo/video/timing.py             # 場面ごとのときだけ（1本のときは飛ばす）
node docs/demo/video/subs.js                            # 場面ごとのときだけ（字幕の長さが変わるため）
VOICE=ext python3 docs/demo/video/audio.py
ffmpeg -y -i docs/demo/video/audio_mix_c_ext.wav -af loudnorm=I=-16:TP=-1.5:LRA=11 -ar 48000 docs/demo/video/audio_final_c_ext.wav
OUT=demo_v3_c_ext.mp4 KARI=0 VOICE=ext python3 docs/demo/video/edit.py
```
- 場面ごとに差し替えたあと Mei の版に戻すときは、`VOICE=mei python3 docs/demo/video/timing.py` から組み直す
- 字幕は台本（DEMO_C.md）の文。読みを変えたら、台本の表も直してから rows.py から組み直す（rows.py は timing の結果を消すので、そのあと tts.py・timing.py も）
- 締めの画面のクレジット（Open JTalk／Mei）は、声を全部差し替えたら figures/src/09_end.html から消して `node docs/demo/figures/render.js 09_end`

### 11/8 提出用に決めた形（作者の判断）
- 0:25 の背景：作者が撮った、正面から見た棟の写真（`photos/danchi.jpg`。横長に合わせて上下を切ると、車のナンバーは画面に入らない）
- 締めの背景：作者が撮った、大きな棟を斜めから見た写真（`photos/end.jpg`）
- 冒頭は掲示板の絵のまま（物語の入り口のため）
- 絵と図の場面は止めて見せる（寄る動きが揺れて見えたため）
- ナレーションは Gemini 3.8 Flash TTS の声「Charon」（作者が5つの声と Mei を聞き比べて選んだ）。`GVOICE=Charon python3 docs/demo/video/gemini_tts.py` で全場面を作り、上の「自分の声・別の音声合成に差し替える」の手順で組み直した。書き出した動画：`demo_v3_c_charon.mp4`。締めのクレジットも Gemini TTS に変えた（Mei に戻すときは figures/src/09_end.html を戻して書き出し直す）
- 写真は公開リポジトリに入れない
