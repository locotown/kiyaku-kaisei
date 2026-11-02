# 評価用データ

`uv run python -m evals.build_r7_gold` で作り直せる。

| ファイル | 内容 |
| --- | --- |
| r7_tantou_before.txt | 改正前（令和6年版相当）の標準管理規約（単棟型）本文。ツールへの入力に使う |
| r7_tantou_after.txt | 改正後（令和7年版）の本文 |
| r7_tantou_gold.json | 条ごとの変更（新設・削除・変更・移動）と、docs/DOMAIN.md の論点・区分（必須／推奨／要確認／その他） |

出典：国土交通省「令和7年改正 改正箇所見え消し（単棟型）」
https://www.mlit.go.jp/jutakukentiku/house/content/001995687.docx を加工して作成
（公共データ利用規約 第1.0版 に基づく。国が作成したものではない）

「その他」は、論点表にない変更（電磁的方法の整理などの「その他所要の改正」）。区分は docs/DOMAIN.md の「要確認」で確定させる。
