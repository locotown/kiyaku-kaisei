#!/usr/bin/env bash
# Codespaces で画面を動かす。
# - リポジトリの最新のコミットを30秒ごとに取り込む（git pull --ff-only。手元で変更していれば取り込まない）
# - コードが変わるとサーバーが自動で再起動する（--reload）。ブラウザは再読み込みするだけでよい
# - 点検・改定案・検討資料・説明文を作っている間と、AI 相談で考えている間は、処理が途中で切れないよう取り込みを待つ
cd "$(dirname "$0")/.." || exit 1
UV="$(command -v uv || echo ~/.local/bin/uv)"

busy() {  # 30分以内に更新された作業のうち、処理中のものがあるか（AI 相談で考え中のものも）
  find private/work -name work.json -mmin -30 2>/dev/null |
    xargs -r grep -lE '"status": "(点検中|改定案作成中|検討資料作成中|説明文作成中)"' | grep -q . && return 0
  find private/consult -name '*.json' -mmin -10 2>/dev/null | xargs -r grep -l '"status": "考え中"' | grep -q .
}

(
  while true; do
    sleep 30
    busy && continue
    before=$(git rev-parse HEAD)
    git pull --ff-only -q 2>/dev/null
    after=$(git rev-parse HEAD)
    if [ "$before" != "$after" ]; then
      # 使う部品（pyproject.toml・uv.lock）が変わったら入れ直す（サーバーの自動の再起動は、部品を入れ直さないため）
      git diff --name-only "$before" "$after" | grep -qE '^(pyproject\.toml|uv\.lock)$' && "$UV" sync -q
      echo "[自動更新] $(git log -1 --format=%s)（ブラウザを再読み込みしてください）"
    fi
  done
) &
trap 'kill $! 2>/dev/null' EXIT

"$UV" run uvicorn app.main:app --port 8000 --reload --reload-dir app --reload-dir core
