# 開発者向け：手元で動かす

技術的な確認のための手順です。審査用には、ログインして使える期限付きの公開版を用意しています（URL とログイン情報は提出フォームに記載）。

## 必要なもの
- [uv](https://docs.astral.sh/uv/)（Python 3.13 と依存はこれで入る）
- Anthropic の API キー（AI の部分を動かすとき。費用はキーの持ち主にかかる）

## 手順
```bash
git clone https://github.com/locotown/kiyaku-kaisei.git && cd kiyaku-kaisei
cp .env.example .env   # ANTHROPIC_API_KEY= の後ろにキーを書く（.env はコミットしない）
uv run uvicorn app.main:app --port 8000
```
ブラウザで `http://127.0.0.1:8000` を開き、トップの「サンプルで試す」から始める（架空の規約）。

- 初めてのキーで点検や改定案づくりをすると、そのキーのワークスペースに AI の設定（スキル・環境・エージェント）を自動で登録する（1分ほど）。登録した ID は `private/agents/` に保存し、キーそのものは保存しない
- 読み込んだ規約・判断の記録・相談の記録は `private/` にだけ保存し、コミットしない
- 費用の目安：点検 約$1、改定案 $1〜8（採用する指摘の数しだい）、相談 1回 約$0.1〜0.9。処理ごとの費用は画面に出る

## テストと評価
```bash
uv run pytest                 # 自動テスト（API を呼ばない）
uv run python -m evals.run_eval_old   # 評価用の規約で点検を評価する（API を使う。evals/）
```

## そのほか
- 審査員向けの公開版（ログイン・期限・費用の上限）：`docs/DEPLOY.md`
- 設計：`docs/ARCHITECTURE.md`
- 作者が開発中に使った起動スクリプト（最新版の自動の取り込みつき）：`scripts/codespace_serve.sh`
