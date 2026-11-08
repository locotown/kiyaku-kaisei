"""審査員向けの公開版のアカウントを作る（11/8）。

  uv run python scripts/make_accounts.py --judges 5 --until 2026-11-12 --out ~/kiyaku_accounts.txt

- 審査員用 judge1〜judgeN と、作者用（管理者。全員の作業を見られ、費用の上限がかからない）を作る
- パスワードはこの場で作る（英数字12文字）
- 画面に出すのは、公開先の環境変数 KIYAKU_ACCOUNTS に貼る値（パスワードはハッシュだけ）
- ID とパスワードの一覧は --out のファイルにだけ書く。リポジトリの外に置き、コミットしない。提出フォームの項目11に使う
"""

from __future__ import annotations

import argparse
import json
import secrets
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.auth import hash_password  # noqa: E402

ALPHABET = string.ascii_letters + string.digits


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judges", type=int, default=5)
    ap.add_argument("--until", required=True, help="使える最後の日（日本時間。例 2026-11-12）")
    ap.add_argument("--admin", default="author", help="作者用のアカウントの ID")
    ap.add_argument("--out", required=True, help="ID とパスワードの一覧を書くファイル（リポジトリの外）")
    a = ap.parse_args()
    out = Path(a.out).expanduser().resolve()
    repo = Path(__file__).resolve().parents[1]
    if repo in out.parents:
        sys.exit("一覧はリポジトリの外に書いてください（コミットしないため）。")
    rows, accounts = [], []
    for uid, admin in [(f"judge{i}", False) for i in range(1, a.judges + 1)] + [(a.admin, True)]:
        pw = "".join(secrets.choice(ALPHABET) for _ in range(12))
        rows.append(f"{uid}\t{pw}\t{a.until}まで{'（管理者）' if admin else ''}")
        accounts.append({"id": uid, "pw": hash_password(pw), "until": a.until, "admin": admin})
    out.write_text("ID\tパスワード\t期限\n" + "\n".join(rows) + "\n", encoding="utf-8")
    print("公開先の環境変数 KIYAKU_ACCOUNTS に、次の1行をそのまま貼ってください：\n")
    print(json.dumps(accounts, ensure_ascii=False, separators=(",", ":")))
    print(f"\nID とパスワードの一覧：{out}（コミットしない）")


if __name__ == "__main__":
    main()
