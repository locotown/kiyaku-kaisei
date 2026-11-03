# 3分デモ動画の台本：パターンC（物語型）

架空の理事長「山本さん」が、法改正の知らせを受け取ってから、総会で規約の改定を可決するまでを、ツールの画面で追う。
見る人が「誰の、どんな困りごとを、どう解決するのか」を、物語として一度に受け取れるようにする。
日本の集合住宅らしさ（掲示板・食卓の規約集・回覧板・総会・判子）を、物語の小道具として見せる。

- 人物・マンション（さくら台マンション）は架空。冒頭の画面に「登場する人物・マンションは架空です」と出す
- 数字と言い方の注意は、パターンA と同じ（docs/DEMO.md の付録）
- 当事者のコメントは撮らない（11/3 決定）

## A・B・C の違い
| | A（初期版） | B（何を作ったかを先に） | C（物語型） |
| --- | --- | --- | --- |
| 入り方 | 日本のマンションの数字 | ツールの名前と成果物 | 理事長に届いた一通の知らせ |
| 何のツールか分かる時点 | 0:45 | 0:00 | 0:26 |
| 背景の数字 | 冒頭 | 冒頭のすぐ後 | 物語の後（「山本さんだけの話ではない」） |

## 全体の流れ（3:00）
| 時間 | 場面 | 伝えること |
| --- | --- | --- |
| 0:00–0:26 | ① 困りごと | 法律が変わり、規約の見直しを求められた。でも、どこを直せばいいか分からない。古いままでは決議が争われるおそれ |
| 0:26–0:36 | ② 出会い | このツールで、直す箇所・改定案・住民への説明まで作れる |
| 0:36–2:05 | ③ 山本さんが使う | 読み込み → 点検 → 指摘と根拠 → 理事会で相談 → 改定案と採点役 → 新旧対照表 → 選ぶ点 → 住民向け説明（回覧板） → 総会で可決 → 最新の規約 |
| 2:05–2:22 | ④ 山本さんだけではない | 約1,600万人。最新の標準に沿った規約は4割ほど |
| 2:22–2:48 | ⑤ 信頼できる理由 | 判断は Claude、正確さはプログラム、決めるのは人。国の改正内容で測った |
| 2:48–3:00 | ⑥ 締め | 専門家に頼めない組合でも、自分たちの手で |

## 場面ごとの台本
### ① 困りごと（0:00–0:26）
| 時間 | 画面 | ナレーション | 英語の字幕 |
| --- | --- | --- | --- |
| 0:00 | 掲示板のお知らせ（10_keijiban） | 理事長の山本さんのもとに、知らせが届きました。「法律の改正に合わせて、管理規約を見直してください」。 | Yamamoto, chair of a condo association, gets a notice: "The law has changed. Please review your bylaws." |
| 0:09 | 食卓の規約集と法律（11_rijicho） | 手元には、分厚い規約集と、難しい法律の条文。どこをどう直せばいいのか、見当もつきません。 | On the table: a thick rulebook and dense legal text. Where to even begin? |
| 0:17 | 同じ場面（寄る） | でも、古い規約のまま総会を開けば、大切な決議が、あとから争われるおそれがあります。 | But under outdated bylaws, even major decisions could be challenged later. |

### ② 出会い（0:26–0:36）
| 時間 | 画面 | ナレーション | 英語の字幕 |
| --- | --- | --- | --- |
| 0:26 | ツールの名前と、成果物の早回し | そこで使ったのが、このツールです。今の規約を読み込むと、直すべき箇所を根拠とともに示し、改定案と住民への説明まで作ります。 | That's where this tool comes in. Upload the bylaws: it shows what must change, with legal citations, and drafts the amendments and an explanation for residents. |

### ③ 山本さんが使う（0:36–2:05）
| 時間 | 画面 | ナレーション | 英語の字幕 |
| --- | --- | --- | --- |
| 0:36 | トップ画面。Word の規約集を読み込む | 山本さんは、今の規約を Word のまま読み込みました。 | Yamamoto uploads the current bylaws as a Word file. |
| 0:42 | 点検の進み具合（早送り） | AI が条文を一つずつ読み、国の標準管理規約と、改正後の法律に照らし合わせます。 | Claude reads each article and checks it against the national model bylaws and the amended law. |
| 0:50 | 指摘の一覧。必須の指摘 | 新しい法律と食い違う箇所は「必須」。どの指摘にも、根拠の条文が付いています。 | Conflicts with the new law are marked "Required" — each with the exact legal article. |
| 0:58 | 根拠の条文・まとめて判断 | どこまで直すかは、理事会のメンバーと相談して決めました。 | Which changes to adopt is decided together with the board. |
| 1:05 | 改定案の作成（早送り）・採点役の確認 | 改定案づくりは、書く AI と、それを確かめる別の AI に分けました。基準を満たすまで、書き直させます。 | One AI drafts the amendments; a separate AI checks them and sends them back until they pass. |
| 1:15 | 新旧対照表 | できあがった新旧対照表は、そのまま総会の資料に使えます。 | The comparison table is ready for the general meeting. |
| 1:24 | 理事会の欄。組合が選ぶ点 | Web 会議を使うかどうかなど、組合が決めるべき点は、理事会で選びました。 | Choices like allowing online meetings were made by the board — not by the AI. |
| 1:34 | 住民向けの説明 | 住民への説明は、法律の言葉ではなく、暮らしの言葉で書かれています。 | The explanation for residents uses everyday words, not legal jargon. |
| 1:42 | 回覧板（12_kairanban） | 山本さんは、それを回覧板で、全ての家に回しました。 | Yamamoto passes it around on the building's circular board. |
| 1:48 | 総会（06_soukai）に「可決」の判子 | そして総会。規約の改定は、可決されました。 | Then, the general meeting. The amendment passes. |
| 1:55 | 最新の規約（Word） | 改正を反映した最新の規約も、附則まで付けて出力します。ここは AI を使わず、プログラムで正確に組み立てます。 | The updated rulebook is produced too — assembled exactly by code, without AI. |

### ④ 山本さんだけではない（2:05–2:22）
| 時間 | 画面 | ナレーション | 英語の字幕 |
| --- | --- | --- | --- |
| 2:05 | 数字（01_japan） | これは、山本さんだけの話ではありません。分譲マンションに住む人は、約1,600万人。 | Yamamoto isn't alone. About 16 million people in Japan live in condominiums. |
| 2:13 | 規約の準拠状況（02_kiyaku） | 国が示す標準の最新版に沿っている規約は、4割ほどにとどまります。 | Only about 4 in 10 bylaws follow the latest national standard. |

### ⑤ 信頼できる理由（2:22–2:48）
| 時間 | 画面 | ナレーション | 英語の字幕 |
| --- | --- | --- | --- |
| 2:22 | 構成図（03_architecture） | 判断が要るところは Claude に、正確さが要るところはプログラムに。決めるのは、人です。 | Judgment goes to Claude, exactness to code — and people make the decisions. |
| 2:34 | 評価（04_eval） | 国が公表した改正内容で測ったところ、法律上必須の箇所に見落としはありませんでした。 | Measured against the government's revision: no legally required change was missed. |

### ⑥ 締め（2:48–3:00）
| 時間 | 画面 | ナレーション | 英語の字幕 |
| --- | --- | --- | --- |
| 2:48 | 締めの画面（09_end） | 専門家に頼めない管理組合でも、自分たちの手で、規約を新しい法律に合わせられるように。 | So that every association — even without experts — can keep its own rules up to date. |
