# kiyaku-kaisei
改正区分所有法（2026年4月施行）に合わせて、管理組合が自分たちで管理規約を見直せるAIツール｜Built with Claude: Japan 2026

## 動かし方（手元のPC）

出力は「総会提案の下書き」であり、法的助言ではありません。

1. [uv](https://docs.astral.sh/uv/) を入れる
2. リポジトリを取得し、`.env.example` を `.env` にコピーして `ANTHROPIC_API_KEY=` にキーを書く（`.env` はコミットしない）
3. エージェントを登録する（初回だけ。登録済みなら不要。ID は `agents/state.json`）
   `uv run python -m agents.setup`
4. 画面を起動する
   `uv run uvicorn app.main:app --port 8000`
5. ブラウザで `http://127.0.0.1:8000` を開く

試すデータ（どちらも公開資料から作った架空のもの）：
- 画面の「サンプル（改正前の標準管理規約）で試す」
- `evals/data/old_collection.txt`（古い規約＋細則3種の規約集）をファイルとして読み込む

読み込んだ規約と判断の記録は `private/work/` に保存されます（コミットされません）。点検・改定案の作成では API を呼ぶため費用がかかります（通しで $2〜3 程度）。

## 評価

- `uv run pytest`（API を呼ばないテスト）
- `uv run python -m evals.run_eval` ほか（`evals/` の各スクリプトの説明を参照。API を呼ぶ）
