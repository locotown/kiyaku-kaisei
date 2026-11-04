# 3分デモ動画の台本：パターンB（何を作ったかを先に見せる）

11/3 の初期版（パターンA：docs/DEMO.md）を見た人から「導入が分かりづらい。何をやるのかが最初にないので、導入の説明が入ってこなかった」という感想があった。
パターンB は、**最初の15秒で「何のツールで、何ができるか」を見せてから**、背景（なぜ必要か）を短く話し、デモに入る。
数字・言い方の注意・素材は、パターンA と同じ（docs/DEMO.md の付録、docs/demo/ASSETS.md）。

## AとBの違い
| | A（初期版） | B |
| --- | --- | --- |
| 最初に見せるもの | 日本のマンションの景色と数字 | ツールの名前と、できあがる4つのもの（指摘・新旧対照表・住民向け説明・最新の規約） |
| 何のツールか分かる時点 | 0:45 | **0:05** |
| 背景（日本のマンション・法改正・古い規約） | 0:00–0:45（45秒） | 0:15–0:42（27秒。デモの「なぜ」として短く） |
| デモ | 0:45–2:30 | 0:42–2:22 |
| 信頼できる理由 | 構成図・評価 | 構成図・評価＋「間違いやすい点を次に活かす」仕組み（検証ループ） |

## 全体の流れ（3:00）
| 時間 | 場面 | 伝えること |
| --- | --- | --- |
| 0:00–0:16 | ① 何を作ったか | 規約を新しい法律に合わせて直すツール。読み込むと、直す箇所・改定案・住民への説明・最新の規約まで作る |
| 0:16–0:55 | ② なぜ必要か | 住民が自分で管理する。法律が変わった。規約は追いついていない。専門家を使えない組合も多い |
| 0:55–2:22 | ③ 使ってみる | 点検 → 指摘と根拠 → 改定案と採点役 → 理事会で選ぶ → 住民向け説明 → 総会後の最新規約 |
| 2:22–2:50 | ④ 信頼できる理由 | 判断は Claude、正確さはプログラム、決めるのは人。国の改正内容で測った。間違いやすい点を次に活かす |
| 2:50–3:00 | ⑤ 締め | 理事になったあなたの規約の見直しを、ととのう規約が支える |

## 場面ごとの台本
11/3 夜：名前「ととのう規約」で書き直した。語りかける相手は、理事や規約見直しの担当になった住民（専門家ではない）。
その人の気がかり（何をどこまで直すか・時間・専門家に頼む予算・総会で揉めないか）に、場面ごとに答える。
約束しすぎない（「可決させる」「専門家が要らない」とは言わない。作るのは総会に出す資料の下書き）。1文は字幕の2行目が短くならないよう44字以内。

### ① 何を作ったか（0:00–0:16）
| 時間 | 画面 | ナレーション | 英語の字幕 |
| --- | --- | --- | --- |
| 0:00 | 団地の景色に、名前「ととのう規約」と説明の一行 | 理事になって、規約を新しい法律に合わせてと頼まれたら。「ととのう規約」があります。 | Asked to update your building's bylaws to the new law? Meet Totonou Kiyaku. |
| 0:07 | 画面の早回し：指摘の一覧 → 新旧対照表 → 住民向けの説明 → 最新の規約 | 今の規約を読み込むと、直す箇所と、改定案や住民への説明の下書きがそろいます。 | Upload your bylaws and get what must change, plus drafts of the amendments and a resident explanation. |

### ② なぜ必要か（0:16–0:55）
| 時間 | 画面 | ナレーション | 英語の字幕 |
| --- | --- | --- | --- |
| 0:16 | 集会室の総会（06_soukai） | マンションのルールは住民の総会で決め、その準備は、理事になった住民が担います。 | Condo rules are voted on at residents' meetings — and prepared by residents serving on the board. |
| 0:23 | 数字（01_japan） | 住む人の高齢化と建物の老朽化を受けて、2026年4月、法律が改正されました。 | As residents and buildings age, Japan revised the law in April 2026. |
| 0:30 | 規約の準拠状況（02_kiyaku） | 2023年の国の調査では、最新の標準に沿っている規約は4割ほどでした。 | A 2023 government survey found only about 4 in 10 bylaws followed the latest standard. |
| 0:36 | 大規模修繕の足場（08_shuuzen） | 古い規約のままでは、総会の決議が、あとから争われるおそれがあります。 | Under outdated bylaws, meeting decisions can be challenged later. |
| 0:42 | 悩む担当者（11_rijicho） | 外部の専門家を活用していない組合は半数を超え、見直しは担当者の肩にかかります。 | Over half of associations don't use outside experts, so the work falls on volunteers. |
| 0:49 | 規約の冊子と手元 | 作った私も、マンションで規約の見直しを担当しています。 | I built this as a member of my own building's bylaw review committee. |

### ③ 使ってみる（0:55–2:22）
| 時間 | 画面 | ナレーション | 英語の字幕 |
| --- | --- | --- | --- |
| 0:55 | トップ画面。Word の規約集を読み込む | 使い方は、今の規約を Word のまま読み込むだけです。 | Just upload your current bylaws as a Word file. |
| 1:01 | 点検の進み具合（早送り） | AI が条文を一つずつ読み、国の標準管理規約と、改正後の法律に照らし合わせます。 | Claude reads each article and checks it against the national model bylaws and the amended law. |
| 1:09 | 指摘の一覧。必須の指摘 | 法律と食い違う箇所は「必須」として、根拠の条文と一緒に示します。 | Conflicts with the new law are marked "Required", each with the exact legal article. |
| 1:16 | 根拠の条文・まとめて判断 | どこまで直すかを決めるのは、委員会のみなさんです。まとめて判断もできます。 | Your committee decides what to adopt — one by one or all at once. |
| 1:23 | 改定案の作成（早送り） | 改定案は、書く AI と確かめる AI の二段構え。基準を満たすまで書き直します。 | One AI drafts; a separate AI checks the draft and sends it back until it meets the criteria. |
| 1:34 | 新旧対照表 | できた新旧対照表は、そのまま総会資料の下書きになります。 | The comparison table becomes the draft for your general meeting. |
| 1:43 | 理事会の欄。組合が選ぶ点 | Web 会議を使うかどうかなど、組合で決めるべき点は、AI が勝手に決めません。 | Choices like allowing online meetings stay with your board — not the AI. |
| 1:54 | 住民向けの説明 | 住民向けの説明も、法律の言葉ではなく、暮らしの言葉で用意します。 | The explanation for residents is written in everyday words, not legal jargon. |
| 2:04 | 総会の結果を記録。「可決」の判子 | 総会で可決したら、結果を記録します。 | After the general meeting, record the result. |
| 2:10 | 最新の規約（Word） | 改正を反映した最新の規約も、附則まで付けて、プログラムで正確に組み立てます。 | The updated rulebook is assembled exactly by code — supplementary provisions included. |

### ④ 信頼できる理由（2:22–2:50）
| 時間 | 画面 | ナレーション | 英語の字幕 |
| --- | --- | --- | --- |
| 2:22 | 構成図（03_architecture） | 判断は Claude に、正確さが要るところはプログラムに。決めるのは人です。 | Judgment goes to Claude, exactness to code — and people make the decisions. |
| 2:31 | 評価（04_eval） | 国が公表した改正内容で測ったところ、法律上必須の箇所に見落としはありませんでした。 | Measured against the government's revision: no legally required change was missed. |
| 2:40 | 改定案の確認結果（採点役のチェックリスト） | 確かめる AI の指摘は集めて、次の改定案づくりに活かしています。 | The checker's feedback is collected to improve the next draft. |

### ⑤ 締め（2:50–3:00）
| 時間 | 画面 | ナレーション | 英語の字幕 |
| --- | --- | --- | --- |
| 2:50 | 締めの画面（09_end） | 理事になったあなたの規約の見直しを、ととのう規約が支えます。 | Totonou Kiyaku — helping every board member put their bylaws in order. |

## 数字の確認
- 「外部の専門家を活用していない組合は、半数を超えます」：国交省「令和5年度マンション総合調査」管18①で、外部専門家を「活用していない」が 53.3%（docs/DEMO.md 付録A）。「使ったことがない」とは言わない（調査は今の活用状況を聞いている）
- そのほかの数字は、パターンA と同じ（付録A・B）

## ほかの案（今回は作らない）
- **パターンC（物語型）**：架空の理事長が「規約を法律に合わせてください」という知らせを受け取る → 分厚い規約と法律の条文に困る → ツールを使う → 理事会 → 総会で可決、の流れで見せる。親しみやすいが、何のツールかが分かるのはBより遅く、人物の映像やイラストが要る
