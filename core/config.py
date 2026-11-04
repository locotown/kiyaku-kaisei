"""設定の読み込み。

APIキーは次の順で探す（値はログや画面に出さない）:
  1. 環境変数 KIYAKU_ANTHROPIC_API_KEY（Claude Code のクラウド環境で使う名前。
     ANTHROPIC_API_KEY という名前は Claude Code 自身の認証用として扱われ、セッションに渡らないため）
  2. 環境変数 ANTHROPIC_API_KEY（手元のPCで .env に書く場合）
.env がリポジトリ直下にあれば読み込む（.env はコミットしない）。
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY_NAMES = ("KIYAKU_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")

# 既定のモデル（docs/ARCHITECTURE.md）
MODEL = os.environ.get("KIYAKU_MODEL", "claude-opus-5-5")


class MissingApiKey(RuntimeError):
    pass


def load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        from dotenv import load_dotenv

        load_dotenv(env, override=False)


def api_key() -> str:
    load_env()
    for name in KEY_NAMES:
        value = os.environ.get(name)
        if value:
            return value
    raise MissingApiKey(
        "APIキーが見つかりません。環境変数 KIYAKU_ANTHROPIC_API_KEY（クラウド環境）"
        "または .env の ANTHROPIC_API_KEY（手元のPC）に設定してください。"
    )


def client():
    """Anthropic のクライアントを作る。"""
    import anthropic

    return anthropic.Anthropic(api_key=api_key())
