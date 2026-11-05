"""Managed Agents（Outcomes）で改定案を作る。

点検で受け付けた指摘をもとに、エージェントが条ごとの改定案を JSON で書き、
/mnt/session/outputs/kaitei.json に保存する。別の採点役（grader）がルーブリックで採点し、
合格するまでエージェントが直す。終わったら Files API でファイルを受け取り、アプリ側でも検査する。

AI の作業（セッション）は Anthropic 側に残るので、通信が切れたり、こちらのサーバーが止まったりしても、
セッションにつなぎ直して続きから進められる（_drive・resume_draft）。最初から作り直すと費用がもう一度かかるため。
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

import anthropic
import httpx2

from core.config import client
from core.draft import DRAFT_SCHEMA, Draft, check
from core.findings import Finding
from core.model import Kiyaku
from core.progress import describe_builtin, describe_tool, draft_plan
from core.quality import RESULT_JA
from core.review import ENFORCED, JST
from core.tools import TOOL_DEFS, ToolHandler

OUTPUT_NAME = "kaitei.json"
MAX_ITERATIONS = 3
RECONNECTS = 6  # 通信が切れたときに、つなぎ直す回数の上限

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

採点のコメントは、前置きから結びまで**すべて日本語**で書く（画面で理事会の担当者がそのまま読む）。項目ごとに「(1) …」の形で書く。

1. /mnt/session/outputs/kaitei.json が存在し、{"amendments": [...], "notes": "..."} の形の JSON である
2. 依頼文で「必須」とされた指摘の論点IDが、すべていずれかの改定の finding_refs に含まれ、その条文で実際に解消されている
3. 改正区分所有法の数値と合っている：規約変更などの特別決議は「組合員総数の過半数かつ議決権総数の過半数の出席」「出席組合員及びその議決権の各4分の3以上」、緊急時の招集通知は「1週間」を下回らない、議案の要領はすべての議案で通知する
4. 指摘と関係のない文言を変えていない（条番号の振り直しをしていない。新設は枝番で追加している）。改定前の文は、末尾の【改定対象の条の現行の文】と一字一句比べて確かめる
5. 各改定の text が、規約の書式（「第○条　」で始まり、第2項以降は「2　」、号は「一　」）に従い、現行規約の言い回し（「組合員」「理事長」など）を引き継いでいる
6. 各改定の reason が、専門家でない理事会の担当者に分かる平易な日本語で、なぜ変えるのかを説明している
7. 各改定に根拠（区分所有法の条文、または標準管理規約の条番号）がある
8. 選択式の規定（電磁的方法の利用の有無など）や、組合が決めるべき事項を勝手に決めず、本文に〔選択〕を付け、choices に選択肢と判断のポイントを書いている
9. 条文中の他の条の参照（「第○条」「前条」）が、改定後の規約で正しい条を指している。細則が規約の条を参照している場合も、改定後の規約の条を正しく指している
11. 各改定の document が正しい（規約本体の改定は「規約」、細則の改定はその細則の題名）。規約で定めるべき事項を細則に、細則で足りる事項を規約に入れていない
10. notes が、スキルの見出し（【決議の進め方】【優先して提案する改定】【組合が選ぶ点】【条・項の番号が変わる箇所】【あわせて検討するとよい点】【使った資料】のうち該当するもの）で整理され、総会提案の下書きであり法的助言ではないことが書かれている
"""


REF_MOUNT = "/mnt/session/uploads/genko_sansho.md"  # 改定案が参照する条の現行の文（自己点検のたびにツールが置く）
MA_BETA = "managed-agents-2026-04-01"


def target_keys(corpus, findings: list[Finding]) -> list[tuple[str, str]]:
    """採用した指摘の対象の条（文書名, 条番号）。"""
    from core.sources import normalize_article_ref

    keys: list[tuple[str, str]] = []
    for f in findings:
        if f.article in ("", "規定なし"):
            continue
        key = (corpus.resolve(f.document) or "規約", normalize_article_ref(f.article))
        if key not in keys:
            keys.append(key)
    return keys


def article_texts(corpus, keys) -> str:
    """条の現行の文を並べる（行頭は字下げして、項目番号と紛れないようにする）。"""
    parts = []
    for doc, num in keys:
        for a in corpus.find(doc, num):
            body = "\n".join("　" + line for line in a.text().splitlines())
            parts.append(f"■ {doc} {a.label}\n{body}")
    return "\n\n".join(parts)


def current_texts(corpus, findings: list[Finding]) -> str:
    """採点役に渡す、改定対象の条の現行の文（ツールが読み込んだ規約から取り出す）。

    採点役は条文を取り寄せるツールを使えないため、確認基準（ルーブリック）に添えて渡す。
    渡すのは採用した指摘の対象の条だけ（改定案を書く AI がもともと取り寄せる範囲）で、規約全体は渡さない。
    """
    body = article_texts(corpus, target_keys(corpus, findings))
    if not body:
        return ""
    return ("\n\n# 【改定対象の条の現行の文】（ツールが読み込んだ規約から取り出したもの。項目4の確認に使う）\n\n"
            + body + "\n\nここにない条を改定している場合は、指摘との関係を申し送りで説明しているかを確かめる。\n"
            + f"改定後の条文が参照する条と、ここにない条を改定した場合のその条の現行の文は {REF_MOUNT} にある（ツールが置く。項目4・9の確認に使う）。"
            "ファイルがない、または載っていない条は、参照先が改定後の規約にあるかだけを確かめる。\n")


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
    precedent: dict = field(default_factory=dict)  # 検証ループ L1：国の改正文を下書きにした条
    checks: list[dict] = field(default_factory=list)  # 検証ループ L2：自己点検（check_draft）のエラー・注意の記録

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
            "precedent": self.precedent,
            "checks": self.checks,
        }


class DraftToolHandler(ToolHandler):
    def __init__(self, kiyaku: Kiyaku, findings: list[Finding], rules: dict[str, Kiyaku] | None = None):
        super().__init__(kiyaku, rules)
        self.adopted = findings
        self.targets = set(target_keys(self.corpus, findings))
        self.check_log: list[dict] = []  # 自己点検のたびのエラー・注意（検証ループ L2 の材料）
        self.client = None
        self.session_id = ""
        self.notify = lambda kind, text: None
        self._resource_id = ""
        self._shared = ""

    def attach(self, client, session_id: str, notify=None) -> None:
        self.client, self.session_id = client, session_id
        if notify:
            self.notify = notify

    def share_references(self, amendments) -> int:
        """改定後の条文が参照する条（対象の条を除く）の現行の文を、採点役が読めるよう作業場所に置く。

        規約全体は渡さず、参照されている条だけを置く。置いた条の数を返す（変わらなければ 0）。
        """
        from core.draft import references
        from core.sources import normalize_article_ref

        # 参照されている条に加え、指摘の対象以外で改正・削除した条（参照合わせなど）も渡す
        changed = {(self.corpus.resolve(a.document) or "規約", normalize_article_ref(a.article))
                   for a in amendments if a.kind in ("改正", "削除")}
        keys = sorted(k for k in (references(amendments, self.corpus) | changed) - self.targets if self.corpus.find(*k))
        text = article_texts(self.corpus, keys)
        if not text or text == self._shared or self.client is None:
            return 0
        content = "# 改定後の条文が参照する条と、指摘の対象以外で改定した条の現行の文（ツールが読み込んだ規約から取り出したもの）\n\n" + text + "\n"
        uploaded = self.client.beta.files.upload(file=("genko_sansho.md", content.encode("utf-8"), "text/markdown"),
                                                 betas=["files-api-2025-04-14", MA_BETA])
        if self._resource_id:
            try:
                self.client.beta.sessions.resources.delete(self._resource_id, session_id=self.session_id, betas=[MA_BETA])
            except Exception:
                pass
        res = self.client.beta.sessions.resources.add(self.session_id, file_id=uploaded.id, type="file",
                                                      mount_path=REF_MOUNT, betas=[MA_BETA])
        self._resource_id, self._shared = res.id, text
        return len(keys)

    def _check_draft(self, draft: dict) -> str:
        result, errors, warnings = check(draft, self.corpus, self.adopted)
        self.check_log.append({"errors": list(errors), "warnings": list(warnings)})
        if result is not None:
            try:
                n = self.share_references(result.amendments)
                if n:
                    self.notify("tool", f"share_references：参照先の条の現行の文を採点役に渡す：{n}条")
            except Exception as e:  # 渡せなくても改定案づくりは続ける（採点役は参照先の有無だけを確かめる）
                self.notify("error", f"参照先の条の文を渡せませんでした：{e}")
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
    from agents.registry import agent_state

    notify = on_event or (lambda kind, text: None)
    state = agent_state(notify)  # この API キーで使うエージェント（初めてのキーなら、ここで登録する）
    c = client()
    handler = DraftToolHandler(kiyaku, findings, rules)
    evaluations: list[dict] = []
    started = time.monotonic()
    plan = draft_plan(len(findings))  # 採用が多いほど、時間と費用の上限を広げる
    deadline = plan["deadline_min"] * 60

    from core.precedent import standard_drafts, to_prompt

    pre = standard_drafts(handler.corpus.main, findings)  # 検証ループ L1
    description = build_description(findings, info, board) + ("\n\n" + to_prompt(pre) if pre["drafts"] else "")

    session = c.beta.sessions.create(
        agent={"type": "agent", "id": state["drafter_id"], "version": state["drafter_version"]},
        environment_id=state["environment_id"],
        title=title,
        budget={"type": "limit", "max_list_cost": {"amount": str(plan["budget_usd"] * 100), "currency": "USD"}},
    )
    notify("session", session.id)
    if pre["drafts"]:
        notify("precedent", f"標準どおりの条 {len(pre['drafts'])}条は、国の改正文を下書きに使います（{'、'.join(d['article'] for d in pre['drafts'][:6])}{' ほか' if len(pre['drafts']) > 6 else ''}）")
    handler.attach(c, session.id, notify)

    kickoff = {
        "type": "user.define_outcome",
        "description": description,
        "rubric": {"type": "text", "content": RUBRIC + current_texts(handler.corpus, findings)},
        "max_iterations": MAX_ITERATIONS,
    }
    stop = _drive(c, session.id, handler, notify, evaluations, started, deadline, plan, kickoff=kickoff)
    return _finish(c, session.id, handler, findings, evaluations, started, stop, pre)


def resume_draft(
    kiyaku: Kiyaku,
    findings: list[Finding],
    session_id: str,
    on_event: Callable[[str, str], None] | None = None,
    rules: dict[str, Kiyaku] | None = None,
) -> DraftResult:
    """途中で止まった改定案づくりを、AI のセッションにつなぎ直して続きから進める。

    セッションは Anthropic 側に残っている。止まっている間に AI が待っていた道具の呼び出し（条文の読み出し・点検など）に
    答えれば、続きから動く。すでに終わっていれば、出来上がった改定案を受け取るだけで、追加の費用はかからない。
    """
    c = client()
    handler = DraftToolHandler(kiyaku, findings, rules)
    notify = on_event or (lambda kind, text: None)
    evaluations: list[dict] = []
    started = time.monotonic()
    plan = draft_plan(len(findings))
    deadline = plan["deadline_min"] * 60  # 再開してからの時間で数える（費用の上限はセッション側で効いている）

    from core.precedent import standard_drafts

    pre = standard_drafts(handler.corpus.main, findings)
    handler.attach(c, session_id, notify)
    notify("session", session_id)
    try:  # 採点役に渡した参照の条の資料が置いてあれば、置き直すときに古いものを外せるよう番号を引き継ぐ
        for r in c.beta.sessions.resources.list(session_id, betas=[MA_BETA]):
            if getattr(r, "mount_path", "") == REF_MOUNT:
                handler._resource_id = r.id
    except anthropic.APIError as e:  # 引き継げなくても続けられる（置き直すときに新しく置く）
        notify("error", f"参照の条の資料の確認に失敗しました：{type(e).__name__}")
    status = c.beta.sessions.retrieve(session_id=session_id).status
    notify("resume", f"途中から再開します（AI の作業の状態：{STATUS_JA.get(status, status)}）")
    if status == "terminated":
        stop = "terminated"
        _catch_up(c, session_id, handler, notify, evaluations, set(), quiet=True)  # 採点の結果だけ集める
    else:
        stop = _drive(c, session_id, handler, notify, evaluations, started, deadline, plan, quiet_history=True)
    return _finish(c, session_id, handler, findings, evaluations, started, stop, pre)


STATUS_JA = {"running": "作業中", "idle": "待機中", "rescheduling": "再開の準備中", "terminated": "終了"}


class _StreamEnded(Exception):
    """ストリームが、終わりの知らせなしに閉じた（つなぎ直す）。"""


def _terminal(event) -> str:
    """AI の作業が終わった（または止まった）知らせなら、その理由。続くなら空。"""
    if event.type == "session.status_terminated":
        return "terminated"
    if event.type == "session.status_idle" and event.stop_reason.type != "requires_action":
        return event.stop_reason.type
    return ""


def _handle(c, session_id: str, handler: DraftToolHandler, event, notify, evaluations: list[dict], quiet: bool = False) -> None:
    """イベント1件に応じる：道具の呼び出しに答え、許可の確認には「許可しない」と返し、採点の結果を記録する。

    quiet：途中から再開したとき、過去の出来事を作業の記録に二重に書かないようにする（答える必要のあるものは書く）。
    """
    etype = event.type
    if etype == "agent.custom_tool_use":
        notify("tool", describe_tool(event.name, dict(event.input or {})))
        try:
            result, is_error = handler.run(event.name, dict(event.input or {})), False
        except Exception as e:
            result, is_error = f"ツールの実行に失敗しました: {e}", True
        c.beta.sessions.events.send(
            session_id=session_id,
            events=[{"type": "user.custom_tool_result", "custom_tool_use_id": event.id,
                     "content": [{"type": "text", "text": result}], "is_error": is_error}],
        )
    elif etype == "agent.tool_use":
        if not quiet:
            notify("builtin", describe_builtin(getattr(event, "name", "")))
        if getattr(event, "evaluated_permission", None) == "ask":
            c.beta.sessions.events.send(
                session_id=session_id,
                events=[{"type": "user.tool_confirmation", "tool_use_id": event.id, "result": "deny"}],
            )
    elif etype == "span.outcome_evaluation_start":
        if not quiet:
            notify("grading", f"採点役が確認しています（{event.iteration + 1}回目）")
    elif etype == "span.outcome_evaluation_end":
        evaluations.append({"iteration": event.iteration, "result": event.result, "explanation": event.explanation})
        if not quiet:
            notify("graded", f"採点役の確認：{RESULT_JA.get(event.result, event.result)}")
    elif etype == "session.error":
        if not quiet:
            notify("error", str(getattr(event, "error", event)))


def _catch_up(c, session_id: str, handler: DraftToolHandler, notify, evaluations: list[dict], seen: set[str],
              quiet: bool) -> str:
    """これまでのイベントを読み、まだ応じていないもの（答えていない道具の呼び出しなど）に応じる。

    通信が切れていた間の出来事を取りこぼさないため（ストリームは過去を送り直さない）。
    すでに終わっていれば、その理由を返す（答えたものがあれば、AI がまた動き出すので空を返す）。
    """
    history = list(c.beta.sessions.events.list(session_id=session_id, order="asc"))
    answered = {getattr(e, "custom_tool_use_id", "") for e in history if e.type == "user.custom_tool_result"}
    confirmed = {getattr(e, "tool_use_id", "") for e in history if e.type == "user.tool_confirmation"}
    acted, last = False, ""
    for e in history:
        if e.type.startswith("session.status_"):
            last = _terminal(e)
        if e.id in seen:
            continue
        seen.add(e.id)
        if e.type == "agent.custom_tool_use" and e.id in answered:
            continue
        if e.type == "agent.tool_use" and (e.id in confirmed or getattr(e, "evaluated_permission", None) != "ask"):
            if not quiet:
                notify("builtin", describe_builtin(getattr(e, "name", "")))
            continue
        if e.type in ("agent.custom_tool_use", "agent.tool_use"):
            acted = True
            _handle(c, session_id, handler, e, notify, evaluations, quiet=False)  # 答えていない呼び出しには答える
        else:
            _handle(c, session_id, handler, e, notify, evaluations, quiet=quiet)
    return "" if acted else last


def _drive(c, session_id: str, handler: DraftToolHandler, notify, evaluations: list[dict], started: float,
           deadline: float, plan: dict, kickoff: dict | None = None, quiet_history: bool = False) -> str:
    """AI の作業のイベントを読み、道具の呼び出しに答えながら、終わるまで進める。止まった理由を返す。

    通信が切れたら、これまでのイベントを読み直してつなぎ直す（同じイベントには二度応じない）。
    kickoff があれば最初に送る（新しく始めるとき）。なければ、過去のイベントから続ける（途中から再開するとき）。
    """
    seen: set[str] = set()
    tries = 0
    while True:
        try:
            with c.beta.sessions.events.stream(session_id=session_id) as stream:  # 先にストリームを開いてから送る・読む
                if kickoff is not None:
                    c.beta.sessions.events.send(session_id=session_id, events=[kickoff])
                    kickoff = None
                else:
                    done = _catch_up(c, session_id, handler, notify, evaluations, seen, quiet=quiet_history)
                    quiet_history = False
                    if done:
                        return done
                for event in stream:
                    if time.monotonic() - started > deadline:
                        notify("stopped", f"時間の上限（{plan['deadline_min']}分）に達したため、AI の作業を止めました")
                        c.beta.sessions.events.send(session_id=session_id, events=[{"type": "user.interrupt"}])
                        return "timeout"
                    tries = 0
                    if event.id not in seen:
                        seen.add(event.id)
                        _handle(c, session_id, handler, event, notify, evaluations)
                    stop = _terminal(event)
                    if stop:
                        return stop
                raise _StreamEnded
        except (_StreamEnded, anthropic.APIConnectionError, anthropic.InternalServerError, httpx2.HTTPError) as e:
            tries += 1
            if tries > RECONNECTS:
                raise
            notify("error", f"AI との通信が切れました。つなぎ直します（{tries}回目）：{type(e).__name__}")
            time.sleep(min(2 ** tries, 30))


def _finish(c, session_id: str, handler: DraftToolHandler, findings: list[Finding], evaluations: list[dict],
            started: float, stop: str, pre: dict) -> DraftResult:
    """出来上がった改定案のファイルを受け取り、アプリ側でも検査して、結果をまとめる。"""
    raw = _download_output(c, session_id)
    if raw is None:
        data, draft, errors, warnings = None, None, [f"{OUTPUT_NAME} が見つかりませんでした。"], []
    else:
        try:
            data = json.loads(raw)
            draft, errors, warnings = check(data, handler.corpus, findings)
        except json.JSONDecodeError as e:
            data, draft, errors, warnings = None, None, [f"{OUTPUT_NAME} が JSON として読めません: {e}"], []
    info_after = c.beta.sessions.retrieve(session_id=session_id)
    usage = info_after.usage.model_dump() if getattr(info_after, "usage", None) else {}
    return DraftResult(
        session_id=session_id, draft=draft, raw=data if raw else None, errors=errors, warnings=warnings,
        evaluations=evaluations, tool_calls=handler.calls, usage=usage,
        elapsed_sec=time.monotonic() - started, stop=stop,
        precedent={"count": len(pre["drafts"]), "articles": [d["article"] for d in pre["drafts"]], "ratio": pre["ratio"]},
        checks=handler.check_log,
    )


def _download_output(c, session_id: str) -> str | None:
    for _ in range(5):  # 待機状態になってからファイルが一覧に出るまで少し遅れることがある
        files = c.beta.files.list(scope_id=session_id, betas=["managed-agents-2026-04-01"])
        for f in files.data:
            if f.filename.endswith(OUTPUT_NAME):
                return c.beta.files.download(f.id).text()
        time.sleep(2)
    return None
