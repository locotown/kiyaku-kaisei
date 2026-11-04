# ととのう規約（kiyaku-kaisei）
管理規約を、改正法に合わせる。

改正区分所有法（2026年4月施行）に合わせて、管理組合が自分たちで管理規約を見直せるAIツール｜Built with Claude: Japan 2026

出力は「総会提案の下書き」であり、法的助言ではありません。

## 動かし方（ブラウザだけで：GitHub Codespaces）

インストール不要で、GitHub 上の作業環境で画面を動かせます。

1. 初回だけ、API キーを Codespaces のシークレットに登録する
   GitHub の Settings → Codespaces → Secrets → New secret
   名前 `KIYAKU_ANTHROPIC_API_KEY`、値に API キー、Repository access でこのリポジトリを選ぶ
2. リポジトリのページで Code → Codespaces → 「Create codespace on （ブランチ名）」
3. 準備（2〜3分）が終わると画面が自動で起動し、ブラウザの新しいタブで開く
   開かないときは、下のパネルの「ポート」タブで 8000 の地球儀アイコンを押す

- 画面は `scripts/codespace_serve.sh` で動きます。リポジトリの更新を30秒ごとに自動で取り込み、サーバーも自動で再起動するので、ブラウザを再読み込みするだけで最新版になります（点検などの処理中は取り込みを待ちます）
- 画面が起動していないときは、ターミナルで `bash scripts/codespace_serve.sh`
- 画面のアドレスは、既定では本人（GitHub にログインした自分）しか開けません
- 使い終わったら codespace を停止する（放置すると無料枠の利用時間を使う）
- 読み込んだ規約は codespace の中の `private/work/` に保存され、コミットされません

## 動かし方（手元のPC）

1. [uv](https://docs.astral.sh/uv/) を入れる
2. リポジトリを取得し、`.env.example` を `.env` にコピーして `ANTHROPIC_API_KEY=` にキーを書く（`.env` はコミットしない）
3. エージェントを登録する（初回だけ。登録済みなら不要。ID は `agents/state.json`）
   `uv run python -m agents.setup`
4. 画面を起動する
   `uv run uvicorn app.main:app --port 8000`
5. ブラウザで `http://127.0.0.1:8000` を開く

試すデータ：トップ画面の「サンプルで試す」から選べます（公開資料をもとにした規約と、架空の規約）。
- 改正前の標準管理規約（87条、細則なし）
- 細則を含む規約集（規約74条＋細則3種＋改正履歴・メモ。`evals/data/old_collection.txt`）
- 長く改正していない古い規約（74条、条番号が標準と違う。`evals/data/old_style_kiyaku.txt`）
- Word（.docx）の規約集（細則を含む規約集と同じ内容。`evals/build_sample_docx.py` で作成）

読み込んだ規約と判断の記録は `private/work/` に保存されます（コミットされません）。点検・改定案の作成では API を呼ぶため費用がかかります（通しで $2〜3 程度）。

## 評価

- `uv run pytest`（API を呼ばないテスト）
- `uv run python -m evals.run_eval` ほか（`evals/` の各スクリプトの説明を参照。API を呼ぶ）
