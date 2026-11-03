# 仮のデモ動画の作り方

台本（docs/DEMO.md の「場面ごとの台本」の表）どおりに、図・イラスト・画面の録画をつなぎ、ナレーションを字幕（日本語＋英語）として焼き込む。
音声はない（ナレーションは本番で録音する）。できた動画は大きいのでコミットしない。

```bash
python3 docs/demo/video/prep.py         # 撮影用の作業データ（架空のサンプルから。private/ に置く）
# サーバーを起動しておき（uv run uvicorn app.main:app --port 8000）、作業データのマンション名を反映：
#   curl -X POST -d "org=さくら台マンション管理組合（架空）" http://127.0.0.1:8000/works/20261103-200000-dm0001/org （dm0004 も）
node docs/demo/video/record.js          # 画面を場面ごとに録画（clips/）
python3 docs/demo/video/rows.py         # 台本の表を読む（rows.json）
pdftoppm -r 110 -f 1 -l 2 -png docs/demo/booklet/sakuradai_kiyaku_kakuu.pdf docs/demo/video/bkp   # 冊子の仮画像の材料
node -e "..."                           # booklet.html を booklet.png に書き出す（仮。手元の撮影に差し替える）
node docs/demo/video/subs.js            # 字幕の画像（subs/）
python3 docs/demo/video/edit.py         # 組み立て → demo_kari.mp4
```

- prep.py は、点検中・改定案作成中の画面を見せるため、実際の点検の記録を時刻だけずらして「処理中」の作業を作る。本番の撮影では、実際に点検・改定案を動かして録画し、早送りする
- 撮影した素材に差し替えるときは、edit.py の VIS（場面ごとの素材）を書き換える
