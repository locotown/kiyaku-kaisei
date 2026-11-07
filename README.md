# ととのう規約（kiyaku-kaisei）
管理規約を、改正法に合わせる。

改正区分所有法（2026年4月施行）に合わせて、管理組合が自分たちで管理規約を見直せるAIツール｜Built with Claude: Japan 2026

出力は「総会提案の下書き」であり、法的助言ではありません。

## 動かし方（ブラウザだけで：GitHub Codespaces）

インストール不要で、GitHub 上の作業環境で画面を動かせます。

1. 初回だけ、API キーを Codespaces のシークレットに登録する
   GitHub の Settings → Codespaces → Secrets → New secret
   名前 `KIYAKU_ANTHROPIC_API_KEY`、値に API キー、Repository access でこのリポジトリを選ぶ
2. リポジトリのページで Code → Codespaces → 「Create codespace on main」（すでに作ってある codespace は、開くだけで最新版を取り込みます）
3. 準備（2〜3分）が終わると画面が自動で起動し、ブラウザの新しいタブで開く
   開かないときは、下のパネルの「ポート」タブで 8000 の地球儀アイコンを押す

- 画面は `scripts/codespace_serve.sh` で動きます。リポジトリの更新を30秒ごとに自動で取り込み、サーバーも自動で再起動するので、ブラウザを再読み込みするだけで最新版になります（点検などの処理中は取り込みを待ちます）
- 画面が起動していないときは、ターミナルで `bash scripts/codespace_serve.sh`
- 画面が 404 になるときは、ターミナルにサーバーの表示（Application startup complete.）があるか確かめる。止まっていれば上のコマンドで起動し、下の「ポート」タブの 8000 の地球のアイコンから開く。それでも開けなければ、codespace を停止して開き直す。ターミナルで `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/` が 200 なのに外から 404 になるときは、Codespaces のポート転送の不具合なので、手元の PC で動かす（下）
- 画面のアドレスは、既定では本人（GitHub にログインした自分）しか開けません
- 使い終わったら codespace を停止する（放置すると無料枠の利用時間を使う）
- 読み込んだ規約は codespace の中の `private/work/` に保存され、コミットされません

## 費用と、自分の API キーで使う仕組み

AI の部分は Anthropic の API で動き、費用は `.env` に入れた API キーの持ち主（Claude Console のアカウント）に、使った分だけかかります（Claude のサブスクリプションとは別）。
管理組合ごとに自分の API キーを入れて使う形を前提にしています。一通り使って約 $2〜10 が目安で、処理ごとの費用は画面に出ます。

- 初めてのキーで点検や改定案づくりをすると、そのキーのワークスペースに AI の設定（スキル・環境・エージェント）を自動で登録します。登録した ID は `private/agents/` に保存し、コミットしません。キーそのものは保存しません
- アプリを更新してスキルや指示文が変わると、次に AI を使うときに登録も自動で更新します
- 開発者のキーでは、リポジトリの `agents/state.json` の登録をそのまま使います（設定を変えたときは `uv run python -m agents.setup` で更新）
- サービスとして提供する形（利用者が API キーを用意しなくてよい形）は、ハッカソン後の計画にしています（docs/plans/今後の展開.md）
- 今回の提出はβ版です。正規版では、法令と国の標準管理規約（解説を含む）を条ごとに整理し、原文で裏付けた独自の知識ベースを裏側で使い、各マンションが自分で決めることを根拠付きで示します。試作では、同じ質問への答えが、国の解説を根拠にした具体的な目安と選択肢に変わりました（1回の費用はほぼ同じ）。知識ベースの中身は非公開で、このリポジトリには入口（core/kb.py）だけがあります

## 動かし方（手元のPC。実物の規約で使うときのおすすめ）

読み込んだ規約が自分の PC から外に出ず、Codespaces のポート転送の不具合（中では動いているのに外から 404 になる）も起きません。Mac の例です。

1. ターミナルで [uv](https://docs.astral.sh/uv/) を入れる
   `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. リポジトリを取得する（初めて git を使うときは、開発ツールのインストールを求められるので入れる）
   `git clone https://github.com/locotown/kiyaku-kaisei.git && cd kiyaku-kaisei`
3. API キーを置く：`cp .env.example .env && open -e .env` で開き、`ANTHROPIC_API_KEY=` の後ろにキーを貼って保存する（`.env` はコミットしない）
   - キーは [Claude Console](https://platform.claude.com/settings/keys) の「キーを作成」→「API キーで続ける」で作る。作ったときに一度だけ表示される。ワークスペースは、エージェントを登録したもの（`agents/state.json`）と同じにする
   - AI の準備（Managed Agents のエージェントの登録）は、初めて点検や改定案づくりをするときに自動で行う（1分ほど）。コマンドは要らない
4. 画面を起動する：`bash scripts/codespace_serve.sh`（30秒ごとに最新版を取り込み、サーバーも自動で再起動する。止めるときは Ctrl+C）
5. ブラウザで `http://127.0.0.1:8000` を開く

Codespace で作った作業を手元に移すとき：Codespace のターミナルで
`cd /workspaces/kiyaku-kaisei && tar czf /tmp/p.tgz private && mv /tmp/p.tgz private/private_backup.tgz`
を実行し、エクスプローラーで `private/private_backup.tgz` を右クリック →「ダウンロード」。手元で
`cd ~/kiyaku-kaisei && tar xzf ~/Downloads/private_backup.tgz` を実行すると `private/` に戻る。

試すデータ：トップ画面の「サンプルで試す」から選べます（公開資料をもとにした規約と、架空の規約）。
- 改正前の標準管理規約（87条、細則なし）
- 細則を含む規約集（規約74条＋細則3種＋改正履歴・メモ。`evals/data/old_collection.txt`）
- 長く改正していない古い規約（74条、条番号が標準と違う。`evals/data/old_style_kiyaku.txt`）
- Word（.docx）の規約集（細則を含む規約集と同じ内容。`evals/build_sample_docx.py` で作成）

読み込んだ規約と判断の記録は `private/work/` に保存されます（コミットされません）。点検・改定案の作成では API を呼ぶため費用がかかります（通しで $2〜3 程度）。

## 評価

- `uv run pytest`（API を呼ばないテスト）
- `uv run python -m evals.run_eval` ほか（`evals/` の各スクリプトの説明を参照。API を呼ぶ）
