# 公開データの出典（SOURCES）

data/public/ に置くファイルは、すべてここに出典を記録する。
実在のマンションの規約・住民名・部屋番号を含むデータは置かない。

## 利用条件
- 国土交通省のコンテンツ：「公共データ利用規約（第1.0版）」（PDL1.0）に準拠。出典を記載して利用できる。加工して使う場合は、加工した旨も記載する（https://www.mlit.go.jp/link.html）
- 法令の本文（e-Gov 法令検索）：法令は著作権の目的とならない（著作権法第13条第1号）

## ファイル一覧（取得日はすべて 2026-11-02）
| ファイル | 内容 | 出典（URL） | SHA-256（先頭12桁） |
| --- | --- | --- | --- |
| mlit/r7_hyojun_kiyaku_tantou.pdf | マンション標準管理規約（単棟型）令和7年10月17日改正、コメント含む | https://www.mlit.go.jp/jutakukentiku/house/content/001999013.pdf | 07e2b29b0f91 |
| mlit/r7_shinkyu_taisho_tantou.pdf | 令和7年改正 新旧対照表（単棟型） | https://www.mlit.go.jp/jutakukentiku/house/content/002002667.pdf | 34802b75621e |
| mlit/r7_mikeshi_tantou.docx | 令和7年改正 改正箇所見え消し（単棟型、Word） | https://www.mlit.go.jp/jutakukentiku/house/content/001995687.docx | 55cb56f78afe |
| mlit/r7_kaisei_gaiyou.pdf | 令和7年マンション標準管理規約改正の概要（◎必須／○望ましい の区分あり） | https://www.mlit.go.jp/jutakukentiku/house/content/001965188.pdf | 6278075c6ba5 |
| mlit/r7_kaisei_tetsuzuki_ryuuiten.pdf | 令和7年改正標準管理規約を踏まえた管理規約の改正を行う場合の手続の留意点 | https://www.mlit.go.jp/jutakukentiku/house/content/001965195.pdf | d3421c980e2b |
| mlit/r7_kaisei_setsumei_slide.pdf | 令和7年マンション標準管理規約改正（スライド形式説明資料） | https://www.mlit.go.jp/jutakukentiku/house/content/002002075.pdf | 60b1139b4567 |
| egov/kubun_shoyu_ho_20260401.json | 建物の区分所有等に関する法律（昭和37年法律第69号）。令和7年法律第47号による改正を反映した、2026-04-01施行時点の本文（e-Gov 法令API v2） | https://laws.e-gov.go.jp/api/2/law_data/337AC0000000069?response_format=json&law_full_text_format=json （改正履歴ID 337AC0000000069_20260401_507AC0000000047） | 9ed547cba32a |

一覧ページ：国土交通省ウェブサイト「マンション標準管理規約」 https://www.mlit.go.jp/jutakukentiku/house/mansionkiyaku.html

## 想定ユーザーの作業（このリポジトリで作ったもの）
| フォルダ | 内容 | 元にしたデータ |
| --- | --- | --- |
| persona_works/ | 架空の想定ユーザー3人が、アプリの「サンプルで試す」で実際に使った作業の記録（判断の履歴・作業の記録・資料・書き込みの写真）。アプリが一覧を開いたときに private/work へ写して「想定ユーザーの作業」として出す | アプリのサンプル（evals/data の架空の規約、公開資料ベースの標準管理規約）だけ。実在のマンションの規約・住民名・部屋番号は含まない。書き込みの写真は、新旧対照表の印刷画面に赤い線を重ねて作ったもの |

## 取り込んでいない資料
- 住民説明用パンフレット（A4版、001971489.pdf）：画像だけのPDFで文字を取り出せないため取り込まない。参照する場合は URL で示す
