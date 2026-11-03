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
| 0:00–0:15 | ① 何を作ったか | 規約を新しい法律に合わせて直すツール。読み込むと、直す箇所・改定案・住民への説明・最新の規約まで作る |
| 0:15–0:42 | ② なぜ必要か | 住民が自分で管理する。法律が変わった。規約は追いついていない。専門家を使えない組合も多い |
| 0:42–2:22 | ③ 使ってみる | 点検 → 指摘と根拠 → 改定案と採点役 → 理事会で選ぶ → 住民向け説明 → 総会後の最新規約 |
| 2:22–2:50 | ④ 信頼できる理由 | 判断は Claude、正確さはプログラム、決めるのは人。国の改正内容で測った。間違いやすい点を次に活かす |
| 2:50–3:00 | ⑤ 締め | 専門家に頼めない組合でも、自分たちの手で |

## 場面ごとの台本
### ① 何を作ったか（0:00–0:15）
| 時間 | 画面 | ナレーション | 英語の字幕 |
| --- | --- | --- | --- |
| 0:00 | 団地の景色に、ツールの名前「管理規約 改正法対応ツール」 | マンションの管理規約を、新しい法律に合わせて直す。それを住民だけでできるようにするツールです。 | A tool that helps residents update their condominium bylaws to Japan's new law — on their own. |
| 0:07 | 画面の早回し：指摘の一覧 → 新旧対照表 → 住民向けの説明 → 最新の規約 | 規約を読み込むと、直す箇所を根拠つきで見つけ、改定案と住民への説明、最新の規約まで作ります。 | Upload the bylaws. It finds what must change, with legal citations, and drafts the amendments, a plain explanation for residents, and the updated rulebook. |

### ② なぜ必要か（0:15–0:42）
| 時間 | 画面 | ナレーション | 英語の字幕 |
| --- | --- | --- | --- |
| 0:15 | 集会室の総会（イラスト） | 日本のマンションは、住民自身が管理し、ルールを総会で決めます。 | In Japan, condominiums are run by the residents, who vote on the rules at general meetings. |
| 0:21 | 数字（1,600万人・4人に1人・約3倍） | 住む人は約1,600万人。高齢化と老朽化に合わせて、2026年4月、法律が変わりました。 | About 16 million people live in them. As residents and buildings age, the law changed in April 2026. |
| 0:29 | 規約の準拠状況のグラフ | でも、最新の標準に沿った規約は4割ほど。古いままだと、総会の決議があとから争われるおそれがあります。 | But only about 4 in 10 bylaws follow the latest standard. Under outdated rules, decisions can be challenged later. |
| 0:37 | 規約の冊子と手元 | 専門家を使ったことがない組合は、半数を超えます。私も、規約の見直しの担当です。 | Over half of associations have never used outside experts. I'm on my own building's rules committee. |

### ③ 使ってみる（0:42–2:22）
| 時間 | 画面 | ナレーション | 英語の字幕 |
| --- | --- | --- | --- |
| 0:42 | トップ画面。Word の規約集を読み込む | 今の規約を、Word のまま読み込みます。 | Upload the current bylaws as a Word file. |
| 0:48 | 点検の進み具合（早送り） | AI が条を一つずつ取り寄せ、国の標準と、改正された法律に照らし合わせます。 | Claude pulls each article and checks it against the national standard and the amended law. |
| 0:56 | 指摘の一覧。必須の指摘を拡大 | 法律に合わず、効力を失うおそれがある箇所は「必須」。必ず根拠の条文を付けます。 | "Required" items conflict with the new law. Every finding cites the exact legal article. |
| 1:05 | 根拠の条文が開く。まとめて判断 | どこまで直すかは、委員会が決めます。 | The committee decides what to adopt. |
| 1:11 | 改定案の作成（早送り）。採点役の確認 | 改定案は、書く AI と、確かめる別の AI に分けました。合格するまで書き直させます。 | One AI drafts; a separate AI grades it against 11 criteria and sends it back until it passes. |
| 1:23 | 新旧対照表 | できあがるのは、総会資料の形の新旧対照表です。 | The result is a side-by-side comparison table, ready for the meeting. |
| 1:33 | 理事会の欄。組合が選ぶ点を選ぶ | Web 会議を使うかのように、組合が選ぶ点は、AI が勝手に決めません。理事会で選びます。 | Choices like allowing online meetings are left to the board — not the AI. |
| 1:45 | 住民向けの説明 | 住民には、法律の言葉ではなく、暮らしの言葉で説明します。 | For residents, it explains the changes in everyday words. |
| 1:57 | 総会の結果を記録。「可決」の判子 | 総会で可決したら、結果を記録します。 | After the general meeting, record the results. |
| 2:04 | 最新の規約（Word） | 改正を反映した最新の規約が、附則付きで出てきます。ここは AI を使わず、正確に組み立てます。 | It produces the updated rulebook — assembled exactly, without AI. |

### ④ 信頼できる理由（2:22–2:50）
| 時間 | 画面 | ナレーション | 英語の字幕 |
| --- | --- | --- | --- |
| 2:22 | 構成図 | 判断は Claude に、正確さが要るところはプログラムに。決めるのは人です。 | Judgment goes to Claude, exactness to code — and people make the decisions. |
| 2:30 | 評価の図 | 国が公表した改正内容で測ると、法律上必須の箇所は見落としなし。採点役の指摘は集めて、次の作成に活かします。 | Measured against the government's revision: no required change missed. The grader's feedback is collected to improve the next draft. |

### ⑤ 締め（2:50–3:00）
| 時間 | 画面 | ナレーション | 英語の字幕 |
| --- | --- | --- | --- |
| 2:50 | 締めの画面 | 専門家に頼めない組合でも、自分たちの手で、規約を法律に合わせられるように。 | So that every association — even without experts — can keep its own rules up to date. |

## 数字の確認
- 「専門家を使ったことがない組合は、半数を超えます」：国交省「令和5年度マンション総合調査」管18①で、外部専門家を「活用していない」が 53.3%（docs/DEMO.md 付録A）
- そのほかの数字は、パターンA と同じ（付録A・B）

## ほかの案（今回は作らない）
- **パターンC（物語型）**：架空の理事長が「規約を法律に合わせてください」という知らせを受け取る → 分厚い規約と法律の条文に困る → ツールを使う → 理事会 → 総会で可決、の流れで見せる。親しみやすいが、何のツールかが分かるのはBより遅く、人物の映像やイラストが要る
