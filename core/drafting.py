"""Managed Agents（Outcomes）で改定案を作る。

点検で受け付けた指摘をもとに、エージェントが条ごとの改定案を JSON で書き、
/mnt/session/outputs/kaitei.json に保存する。別の採点役（grader）がルーブリックで採点し、
合格するまでエージェントが直す。終わったら Files API でファイルを受け取り、アプリ側でも検査する。
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from core.config import ROOT, client
from core.draft import DRAFT_SCHEMA, Draft, check
from core.findings import Finding
from core.model import Kiyaku
from core.review import BUDGET_CENTS, DEADLINE_SEC, ENFORCED, JST
from core.tools import TOOL_DEFS, ToolHandler

STATE = ROOT / "agents/state.json"
OUTPUT_NAME = "kaitei.json"
MAX_ITERATIONS = 3

CHECK_TOOL = {
    "type": "custom",
    "name": "check_draft",
    "description": (
        "改定案の JSON を機械的に検査する（形式、条番号、根拠の実在、必須の指摘への対応、同じ条の重複）。"
        "kaitei.json に保存する前に必ず呼び、エラーがなくなるまで直す。"
    ),
    "input_schema": {"type": "object", "properties": {"draft": DRAFT_SCHEMA}, "required": ["draft"]},
}
DRAFTER_TOOLS = [t for t in TOOL_DEFS if t["name"] != "record_findings"] + [CHECK_TOOL]

RUBRIC = """# 改定案のルーブリック（各項目を独立に採点する）

1. /mnt/session/outputs/kaitei.json が存在し、{"amendments": [...], "notes": "..."} の形の JSON である
2. 依頼文で「必須」とされた指摘の論点IDが、すべていずれかの改定の finding_refs に含まれ、その条文で実際に解消されている
3. 改正区分所有法の数値と合っている：規約変更などの特別決議は「組合員総数の過半数かつ議決権総数の過半数の出席」「出席組合員及びその議決権の各4分の3以上」、緊急時の招集通知は「1週間」を下回らない、議案の要領はすべての議案で通知する
4. 指摘と関係のない文言を変えていない（条番号の振り直しをしていない。新設は枝番で追加している）
5. 各改定の text が、規約の書式（「第○条　」で始まり、第2項以降は「2　」、号は「一　」）に従い、現行規約の言い回し（「組合員」「理事長」など）を引き継いでいる
6. 各改定の reason が、専門家でない理事会の担当者に分かる平易な日本語で、なぜ変えるのかを説明している
7. 各改定に根拠（区分所有法の条文、または標準管理規約の条番号）がある
8. 選択式の規定（電磁的方法の利用の有無など）や、組合が決めるべき事項を勝手に決めず、本文に〔選択〕を付け、choices に選択肢と判断のポイントを書いている
9. 条文中の他の条の参照（「第○条」「前条」）が、改定後の規約で正しい条を指している。細則が規約の条を参照している場合も、改定後の規約の条を正しく指している
11. 各改定の document が正しい（規約本体の改定は「規約」、細則の改定はその細則の題名）。規約で定めるべき事項を細則に、細則で足りる事項を規約に入れていない
10. notes が、スキルの見出し（【決議の進め方】【優先して提案する改定】【組合が選ぶ点】【条・項の番号が変わる箇所】【あわせて検討するとよい点】【使った資料】のうち該当するもの）で整理され、総会提案の下書きであり法的助言ではないことが書かれている
"""


@dataclass
class DraftResult:
    session_id: str
    draft: Draft | None
    raw: dict | None
    errors: list[str]
    warnings: list[str]
    evaluations: list[dict] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    elapsed_sec: float = 0.0
    stop: str = ""

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "draft": self.draft.to_dict() if self.draft else None,
            "raw": self.raw if not self.draft else None,
            "errors": self.errors,
            "warnings": self.warnings,
            "evaluations": self.evaluations,
            "tool_calls": self.tool_calls,
            "usage": self.usage,
            "elapsed_sec": round(self.elapsed_sec, 1),
            "stop": self.stop,
        }


class DraftToolHandler(ToolHandler):
    def __init__(self, kiyaku: Kiyaku, findings: list[Finding], rules: dict[str, Kiyaku] | None = None):
        super().__init__(kiyaku, rules)
        self.adopted = findings

    def _check_draft(self, draft: dict) -> str:
        result, errors, warnings = check(draft, self.corpus, self.adopted)
        if errors:
            return json.dumps({"結果": "エラーあり", "エラー": errors, "注意": warnings}, ensure_ascii=False)
        return json.dumps({"結果": "検査に合格", "改定の数": len(result.amendments), "注意": warnings,
                           "次にすること": f"この JSON を /mnt/session/outputs/{OUTPUT_NAME} に保存する"}, ensure_ascii=False)


def build_description(findings: list[Finding], info: dict, board: str = "") -> str:
    today = datetime.now(JST).date()
    compact = [
        {k: v for k, v in f.to_dict().items() if k in (
            "document", "article", "topic_id", "category", "issue", "law_basis", "standard_basis", "where", "proposal", "choice_needed", "choice_note")}
        for f in findings
    ]
    return "\n".join([
        "次の指摘（採用済み）をもとに、マンション管理規約の改定案を条ごとに作ってください。",
        f"基準日：{today.year}年{today.month}月{today.day}日"
        + ("（改正区分所有法は施行済み）" if today >= ENFORCED else "（改正区分所有法の施行前）"),
        "",
        "## マンションの基本情報",
        *[f"- {k}：{v}" for k, v in info.items()],
        "",
        "## 作り方",
        "- スキル kiyaku-kaisei の「改定案の書き方」に従う",
        "- 現行規約は get_articles、改正後の標準管理規約は get_standard_articles、区分所有法は get_law_articles で取得してから書く",
        "- 1つの条に複数の指摘がある場合は、1つの改定にまとめる（finding_refs に複数の論点IDを入れる）",
        f"- 書き終えたら check_draft で検査し、エラーがなくなったら /mnt/session/outputs/{OUTPUT_NAME} に保存する",
        "",
        "## 細則",
        ("この規約集には細則があります（list_rules で確認）。細則の改定は document に細則の題名を入れてください。"
         if any(f.document != "規約" for f in findings) else "（指摘の対象は規約本体です。細則がある場合は list_rules で確認できます）"),
        "",
        *(["## 理事会の判断（必ず反映する。「見送り」の議題の改定は含めない。「修正して採用」「要修正」はメモの内容で直す。選んだ案があればその案で書き、〔選択〕を外す）",
            board, ""] if board else []),
        "## 採用済みの指摘（JSON）",
        json.dumps(compact, ensure_ascii=False),
    ])


def run_draft(
    kiyaku: Kiyaku,
    findings: list[Finding],
    info: dict,
    on_event: Callable[[str, str], None] | None = None,
    title: str = "改定案の作成",
    rules: dict[str, Kiyaku] | None = None,
    board: str = "",
) -> DraftResult:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    c = client()
    handler = DraftToolHandler(kiyaku, findings, rules)
    notify = on_event or (lambda kind, text: None)
    evaluations: list[dict] = []
    started = time.monotonic()
    stop = ""

    session = c.beta.sessions.create(
        agent={"type": "agent", "id": state["drafter_id"], "version": state["drafter_version"]},
        environment_id=state["environment_id"],
        title=title,
        budget={"type": "limit", "max_list_cost": {"amount": BUDGET_CENTS, "currency": "USD"}},
    )
    notify("session", session.id)

    with c.beta.sessions.events.stream(session_id=session.id) as stream:
        c.beta.sessions.events.send(
            session_id=session.id,
            events=[{
                "type": "user.define_outcome",
                "description": build_description(findings, info, board),
                "rubric": {"type": "text", "content": RUBRIC},
                "max_iterations": MAX_ITERATIONS,
            }],
        )
        for event in stream:
            if time.monotonic() - started > DEADLINE_SEC:
                stop = "timeout"
                c.beta.sessions.events.send(session_id=session.id, events=[{"type": "user.interrupt"}])
                break
            etype = event.type
            if etype == "agent.custom_tool_use":
                notify("tool", event.name)
                try:
                    result, is_error = handler.run(event.name, dict(event.input or {})), False
                except Exception as e:
                    result, is_error = f"ツールの実行に失敗しました: {e}", True
                c.beta.sessions.events.send(
                    session_id=session.id,
                    events=[{"type": "user.custom_tool_result", "custom_tool_use_id": event.id,
                             "content": [{"type": "text", "text": result}], "is_error": is_error}],
                )
            elif etype == "agent.tool_use":
                notify("builtin", getattr(event, "name", ""))
                if getattr(event, "evaluated_permission", None) == "ask":
                    c.beta.sessions.events.send(
                        session_id=session.id,
                        events=[{"type": "user.tool_confirmation", "tool_use_id": event.id, "result": "deny"}],
                    )
            elif etype == "span.outcome_evaluation_start":
                notify("grading", f"採点 {event.iteration + 1}回目")
            elif etype == "span.outcome_evaluation_end":
                evaluations.append({"iteration": event.iteration, "result": event.result, "explanation": event.explanation})
                notify("graded", f"{event.result}：{event.explanation[:200]}")
            elif etype == "session.error":
                notify("error", str(getattr(event, "error", event)))
            elif etype == "session.status_idle":
                if event.stop_reason.type != "requires_action":
                    stop = event.stop_reason.type
                    break
            elif etype == "session.status_terminated":
                stop = "terminated"
                break

    raw = _download_output(c, session.id)
    if raw is None:
        draft, errors, warnings = None, [f"{OUTPUT_NAME} が見つかりませんでした。"], []
    else:
        try:
            data = json.loads(raw)
            draft, errors, warnings = check(data, handler.corpus, findings)
        except json.JSONDecodeError as e:
            data, draft, errors, warnings = None, None, [f"{OUTPUT_NAME} が JSON として読めません: {e}"], []
    info_after = c.beta.sessions.retrieve(session_id=session.id)
    usage = info_after.usage.model_dump() if getattr(info_after, "usage", None) else {}
    return DraftResult(
        session_id=session.id, draft=draft, raw=data if raw else None, errors=errors, warnings=warnings,
        evaluations=evaluations, tool_calls=handler.calls, usage=usage,
        elapsed_sec=time.monotonic() - started, stop=stop,
    )


def _download_output(c, session_id: str) -> str | None:
    for _ in range(5):  # 待機状態になってからファイルが一覧に出るまで少し遅れることがある
        files = c.beta.files.list(scope_id=session_id, betas=["managed-agents-2026-04-01"])
        for f in files.data:
            if f.filename.endswith(OUTPUT_NAME):
                return c.beta.files.download(f.id).text()
        time.sleep(2)
    return None
