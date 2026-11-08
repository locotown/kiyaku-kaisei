# デモ動画の図とイラスト

1920×1080 の PNG。字幕を重ねるため、下の210pxは空けてある。数字はすべて一次資料か evals/results の値（出典は各図の下と docs/DEMO.md の付録）。

| ファイル | 場面（docs/DEMO.md） | 内容 |
| --- | --- | --- |
| 01_japan.png | ① 0:12 | 約1,600万人／世帯主の4人に1人が70歳以上／築40年超は20年で約3倍 |
| 02_kiyaku.png | ② 0:22 | 標準管理規約への準拠状況（最新の版 42.3%・古い版 49.8%・沿っていない／不明 8.0%） |
| 03_architecture.png | ⑦ 2:30 | 構成図（人・Claude・プログラムの3段） |
| 04_eval.png | ⑦ 2:39 | 評価（法律で必ず直す論点 8/8（3本の規約すべて）・根拠の正しさ100%・細則の問題3/3。README の評価とそろえた） |
| 09_end.png・09_end_fg.png | パターンC ⑥ 締め | 名前・URL・「総会提案の下書きであり、法的助言ではありません」・クレジット。09_end_fg.png は背景なし（作者の写真に重ねる。docs/demo/video/README.md） |
| 05_danchi.png | ① 0:00・⑧ 2:50 | 団地の景色のイラスト（布団・洗濯物・電柱）。11/8 v3 で「仮」の印を外した（render.js）。作者の写真に差し替えられる（docs/demo/video/README.md） |
| 06_soukai.png | ① 0:05 | 集会室での総会のイラスト（さくら台マンション管理組合（架空）の第25期定期総会） |
| 07_law.png | ① 0:17 | 区分所有法 第31条第1項の条文（e-Gov の正文どおり） |
| 07s_stamp_shikou.png | ① 0:17 | 「2026.4.1 施行」の判子（背景は透明。編集で押す動きを付けて 07_law.png に重ねる） |
| 07s_stamp_kaketsu.png | ⑥ 2:15 | 「第25期総会 可決」の判子（背景は透明） |
| 08_shuuzen.png 〔仮〕 | ② 0:31 | 大規模修繕の足場のイラスト。**素材集の写真か撮影に差し替える** |

| 10_keijiban.png | パターンC 0:00 | マンションの掲示板。「区分所有法の改正に伴う管理規約の見直しについて」のお知らせ（「登場する人物・マンションは架空です」の注記つき） |
| 11_rijicho.png | パターンC 0:09 | 食卓で、分厚い規約集と区分所有法の条文を前に悩む理事長（後ろ姿） |
| 12_kairanban.png | パターンC 1:42 | 回覧板。「管理規約の改定について」と、読んだ家の「済」の印（部屋番号は架空） |

〔仮〕は右上に「仮」の印がある。差し替えたら、この表と docs/demo/ASSETS.md を直す。

## 作り直し方
```bash
python3 docs/demo/figures/make_architecture.py   # 構成図の HTML を作る（箱と矢印の位置を計算）
python3 docs/demo/figures/make_illustrations.py  # イラストと判子の HTML を作る
node docs/demo/figures/render.js                 # src/*.html を PNG に書き出す
```
- フォントは Noto Sans JP（jsDelivr の @fontsource から読み込む。書き出しにはネットワークが要る）
- 色は2色だけ：青（Claude・事実）、オレンジ（人・古い版）。灰色は「その他」とプログラム
- 簡素な版。デザインの見直し（docs/DESIGN_IDEAS.md）で見た目の方向が決まったら、src/common.css の色と字体を合わせる
