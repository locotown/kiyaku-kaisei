"""使う API キーに合わせて、Managed Agents の登録（Skill・環境・エージェント）を選ぶ。なければ自動で登録する。

公開の形：管理組合が自分の API キーで使う（docs/SUBMISSION.md）。エージェントは API キーのワークスペースごとに
登録が要るので、利用者が手でコマンドを実行しなくて済むよう、初めて AI を使うときにここで登録する。

- 開発者のキー：リポジトリの agents/state.json の登録が見えるので、そのまま使う（登録はしない）
- それ以外のキー：agents/state.json の登録が見えない → その場で登録し、ID を private/agents/ に保存する（コミットしない）
- アプリを更新してスキルや指示文が変わったら、自動で登録したエージェントも更新する（設定の指紋で見分ける）

API キーそのものは保存しない。ファイル名には、キーから作った指紋（元のキーに戻せない）だけを使う。
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable

import anthropic

from core.config import ROOT, api_key, client

COMMITTED = ROOT / "agents/state.json"
PRIVATE = ROOT / "private/agents"
NOT_MINE = (anthropic.NotFoundError, anthropic.PermissionDeniedError)  # 別のワークスペースの登録は、見えない
_lock = threading.Lock()


def _fingerprint() -> str:
    return hashlib.sha256(api_key().encode("utf-8")).hexdigest()[:16]


def _committed() -> dict:
    return json.loads(COMMITTED.read_text(encoding="utf-8")) if COMMITTED.exists() else {}


def _visible(c, state: dict) -> bool:
    """このキーで、登録済みのエージェントが見えるか（見えれば、同じワークスペース）。"""
    if not state.get("agent_id") or not state.get("drafter_id"):
        return False
    try:
        c.beta.agents.retrieve(state["agent_id"])
        c.beta.agents.retrieve(state["drafter_id"])
        return True
    except NOT_MINE:
        return False


def agent_state(notify: Callable[[str, str], None] | None = None) -> dict:
    """このキーで使うエージェントの ID（agent_id・drafter_id・environment_id など）。なければ登録してから返す。"""
    from agents.setup import config_hash, ensure

    say = notify or (lambda kind, text: None)
    path = PRIVATE / f"state-{_fingerprint()}.json"
    with _lock:
        saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if saved.get("source") == "committed":  # 開発者のキー：いつも最新の agents/state.json を使う
            return _committed()
        if saved.get("source") == "own" and saved.get("config") == config_hash():
            return saved["state"]
        c = client()
        if not saved:
            committed = _committed()
            if _visible(c, committed):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"source": "committed"}, ensure_ascii=False), encoding="utf-8")
                return committed
        first = not saved
        say("setup", "はじめて使う API キーなので、AI の準備（エージェントの登録）をしています。1分ほどかかります" if first
            else "アプリが更新されたので、AI の設定を新しくしています")
        try:
            state = ensure(c, saved.get("state", {}), log=lambda text: say("setup", text))
        except anthropic.APIError as e:
            raise RuntimeError(
                "この API キーでは、AI の準備（エージェントの登録）ができませんでした。"
                "Claude Console で、キーが有効か、Managed Agents が使えるかを確かめてください。"
                f"（{type(e).__name__}）") from e
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"source": "own", "config": config_hash(), "state": state}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        say("setup", "AI の準備ができました")
        return state


def status() -> dict:
    """画面や確認用：このキーの登録の状態（登録はしない）。"""
    path = PRIVATE / f"state-{_fingerprint()}.json"
    if not path.exists():
        return {"registered": False}
    saved = json.loads(path.read_text(encoding="utf-8"))
    return {"registered": True, "source": saved.get("source")}


__all__ = ["COMMITTED", "NOT_MINE", "PRIVATE", "agent_state", "status"]

