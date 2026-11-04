"""Managed Agents のセッションで、規約の点検（指摘の洗い出し）を行う。

流れ:
  1. 保存済みのエージェント（agents/state.json）でセッションを作る（上限金額つき）
  2. イベントの受信を始めてから、点検の依頼を送る
  3. エージェントがカスタムツールを呼ぶたびに、アプリ側で実行して結果を返す
  4. エージェントが作業を終えて待機状態になったら終了する
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from core.config import ROOT, client
from core.findings import Finding
from core.model import Kiyaku
from core.progress import describe_builtin, describe_tool
from core.tools import ToolHandler

STATE = ROOT / "agents/state.json"
BUDGET_CENTS = "500"  # 1セッションの上限 $5.00（公開価格ベース）
DEADLINE_SEC = 30 * 60
JST = timezone(timedelta(hours=9))
ENFORCED = date(2026, 4, 1)  # 改正区分所有法の施行日


@dataclass
class ReviewResult:
    session_id: str
    findings: list[Finding]
    rejected: list[dict]
    summary: str
    tool_calls: list[str]
    usage: dict = field(default_factory=dict)
    elapsed_sec: float = 0.0
    stop: str = ""

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "findings": [f.to_dict() for f in self.findings],
            "rejected": self.rejected,
            "summary": self.summary,
            "tool_calls": self.tool_calls,
            "usage": self.usage,
            "elapsed_sec": round(self.elapsed_sec, 1),
            "stop": self.stop,
        }


def build_request(info: dict, today: date | None = None) -> str:
    today = today or datetime.now(JST).date()
    lines = [
        "次のマンションの現行管理規約を点検し、改正区分所有法（2026年4月施行）と",
        "マンション標準管理規約（2025年10月改正・単棟型）への対応が必要な箇所を、根拠付きで洗い出してください。",
        "",
        f"## 基準日：{today.year}年{today.month}月{today.day}日",
    ]
    if today >= ENFORCED:
        lines.append("改正法はすでに施行されています。これから招集する総会は、規約の改正を含め、改正法の定足数・決議要件で決議します"
                     "（改正前の規約の要件で決議できるのは、2026年3月31日までに招集手続きを始めた総会だけです）。")
    else:
        lines.append("改正法の施行（2026年4月1日）前です。総会の招集手続きを3月31日までに始めるか、4月1日以降に始めるかで、"
                     "規約改正の手続きが変わります。")
    lines += [
        "",
        "## マンションの基本情報",
    ]
    for k, v in info.items():
        lines.append(f"- {k}：{v}")
    lines += [
        "",
        "## お願い",
        "- スキル kiyaku-kaisei の手順に従い、論点表のすべての論点を確認してください",
        "- 細則がある場合（list_rules）は、細則も点検してください（スキルの「細則の点検」）",
        "- 指摘はすべて record_findings で記録してください",
        "- 最後に、指摘の件数（必須・推奨・参考の内訳）と、担当者が判断すべき点を短くまとめてください",
    ]
    return "\n".join(lines)


def run_review(
    kiyaku: Kiyaku,
    info: dict,
    on_event: Callable[[str, str], None] | None = None,
    title: str = "規約の点検",
    rules: dict[str, Kiyaku] | None = None,
) -> ReviewResult:
    """点検を実行する。on_event(種類, 内容) で進み具合を受け取れる。"""
    state = json.loads(STATE.read_text(encoding="utf-8"))
    c = client()
    handler = ToolHandler(kiyaku, rules)
    notify = on_event or (lambda kind, text: None)
    texts: list[str] = []
    started = time.monotonic()

    session = c.beta.sessions.create(
        agent={"type": "agent", "id": state["agent_id"], "version": state["agent_version"]},
        environment_id=state["environment_id"],
        title=title,
        budget={"type": "limit", "max_list_cost": {"amount": BUDGET_CENTS, "currency": "USD"}},
    )
    notify("session", session.id)
    stop = ""

    with c.beta.sessions.events.stream(session_id=session.id) as stream:
        c.beta.sessions.events.send(
            session_id=session.id,
            events=[{"type": "user.message", "content": [{"type": "text", "text": build_request(info)}]}],
        )
        for event in stream:
            if time.monotonic() - started > DEADLINE_SEC:
                stop = "timeout"
                c.beta.sessions.events.send(session_id=session.id, events=[{"type": "user.interrupt"}])
                break
            etype = event.type
            if etype == "agent.message":
                for block in event.content:
                    if block.type == "text":
                        texts.append(block.text)
                        notify("message", block.text)
            elif etype == "agent.custom_tool_use":
                notify("tool", describe_tool(event.name, dict(event.input or {})))
                before = len(getattr(handler, "findings", []) or [])
                try:
                    result = handler.run(event.name, dict(event.input or {}))
                    is_error = False
                    if event.name == "record_findings":
                        total = len(handler.findings)
                        notify("found", f"指摘を{total - before}件受け付け（合計{total}件）")
                except Exception as e:  # ツールの失敗はエージェントに返して直させる
                    result, is_error = f"ツールの実行に失敗しました: {e}", True
                c.beta.sessions.events.send(
                    session_id=session.id,
                    events=[{
                        "type": "user.custom_tool_result",
                        "custom_tool_use_id": event.id,
                        "content": [{"type": "text", "text": result}],
                        "is_error": is_error,
                    }],
                )
            elif etype == "agent.tool_use":
                notify("builtin", describe_builtin(getattr(event, "name", "")))
                if getattr(event, "evaluated_permission", None) == "ask":
                    # 読み取り以外のツールは無効にしてある。念のため、確認を求められたら拒否する
                    c.beta.sessions.events.send(
                        session_id=session.id,
                        events=[{"type": "user.tool_confirmation", "tool_use_id": event.id, "result": "deny"}],
                    )
            elif etype == "session.error":
                notify("error", str(getattr(event, "error", event)))
            elif etype == "session.status_idle":
                reason = event.stop_reason.type
                if reason != "requires_action":
                    stop = reason
                    break
            elif etype == "session.status_terminated":
                stop = "terminated"
                break

    info_after = c.beta.sessions.retrieve(session_id=session.id)
    usage = info_after.usage.model_dump() if getattr(info_after, "usage", None) else {}
    return ReviewResult(
        session_id=session.id,
        findings=handler.findings,
        rejected=handler.rejected,
        summary=texts[-1] if texts else "",
        tool_calls=handler.calls,
        usage=usage,
        elapsed_sec=time.monotonic() - started,
        stop=stop,
    )
