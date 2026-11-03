# デモ動画の図

1920×1080 の PNG。字幕を重ねるため、下の160pxは空けてある。数字はすべて一次資料か evals/results の値（出典は各図の下と docs/DEMO.md の付録）。

| ファイル | 場面（docs/DEMO.md） | 内容 |
| --- | --- | --- |
| 01_japan.png | ① 0:12 | 約1,600万人／世帯主の4人に1人が70歳以上／築40年超は20年で約3倍 |
| 02_kiyaku.png | ② 0:22 | 標準管理規約への準拠状況（最新の版 42.3%・古い版 49.8%・沿っていない／不明 8.0%） |
| 03_architecture.png | ⑦ 2:30 | 構成図（人・Claude・プログラムの3段） |
| 04_eval.png | ⑦ 2:39 | 評価（必須の見落とし0件・根拠の正しさ96.3%・細則の問題3/3） |

## 作り直し方
```bash
python3 docs/demo/figures/make_architecture.py   # 構成図の HTML を作る（箱と矢印の位置を計算）
node docs/demo/figures/render.js                 # src/*.html を PNG に書き出す
```
- フォントは Noto Sans JP（jsDelivr の @fontsource から読み込む。書き出しにはネットワークが要る）
- 色は2色だけ：青（Claude・事実）、オレンジ（人・古い版）。灰色は「その他」とプログラム
- 簡素な版。デザインの見直し（docs/DESIGN_IDEAS.md）で見た目の方向が決まったら、src/common.css の色と字体を合わせる
