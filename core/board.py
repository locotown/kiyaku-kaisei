"""理事会（または規約見直し委員会）で検討するための資料と、その判断の記録。

住民向けの説明の前に、改定案を3段に分けて理事会で議論し、方針を固める。
  ① 法律の改正に合わせる変更 … 理解する（変えないことはできない）
  ② 暮らしや運営に関わる変更 … 判断する（採用／修正して採用／見送り。〔選択〕の箇所はどの案にするか）
  ③ 古い規定や表現の整理     … 確認する（内容が変わらないことの確認）
①に入るかどうかは AI に任せず、改定案の必須の論点から機械的に決める。②と③の振り分けと説明文は AI が書く。
資料の作成は Messages API の1回の呼び出し（構造化出力）。
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from core.config import MODEL, client
from core.draft import CHOICE_MARK, Draft
from core.explain import _ref_key, ref_name
from core.review import ENFORCED, JST

TIERS = ["法律の改正に合わせる変更", "暮らしや運営に関わる変更", "古い規定や表現の整理"]
TIER_TASK = {
    TIERS[0]: ("理解する", "改正された法律に合わせるため、変えないことはできません。何が求められているかを理解し、質問があれば確認します。"),
    TIERS[1]: ("判断する", "法律上は必須ではありません。採用する・修正して採用する・見送るのいずれかを決め、〔選択〕の箇所はどの案にするかを決めます。"),
    TIERS[2]: ("確認する", "参照する条の番号や言い回しを整えるもので、内容は変わりません。そのことを確認します。"),
}
DECISIONS = {
    TIERS[0]: ["理解した"],
    TIERS[1]: ["採用", "修正して採用", "見送り"],
    TIERS[2]: ["確認した", "要修正"],
}
NEEDS_REDRAFT = {"修正して採用", "要修正"}
DISCLAIMER = "この資料は総会提案の下書きであり、法的助言ではありません。改正区分所有法に抵触しない範囲では、内容は各管理組合が自由に決められます。"


class BoardItem(BaseModel):
    tier: Literal["法律の改正に合わせる変更", "暮らしや運営に関わる変更", "古い規定や表現の整理"]
    title: str = Field(description="議題の見出し。例：「総会の決め方（特別決議の要件と定足数）」")
    articles: list[str] = Field(description="関係する改定の ref（改定案の ref をそのまま）")
    summary: str = Field(description="何をどう変えるか。2〜4文")
    points: list[str] = Field(description="①は理解のポイント（法律が求めること、変えないと何が起きるか）、②は判断のポイント（利点・注意点・暮らしへの影響・判断の目安）、③は確認のポイント（何を整えたか、内容が変わらないこと）。各1〜2文、2〜5個")
    options: list[str] = Field(description="②のみ：選べる案（採用する場合の内容、修正するならどんな修正があり得るか、見送った場合どうなるか）。〔選択〕の箇所があれば、その選択肢もここに書く。①③は空")
    questions: list[str] = Field(description="理事会で出そうな質問と、その答えの要点（「Q：…／A：…」の形）。0〜3個")


class BoardPaper(BaseModel):
    title: str = Field(description="資料の題名。例：「管理規約の改定案について（理事会検討資料）」")
    intro: str = Field(description="検討の目的と進め方（①→②→③の順に検討すること）。3〜4文")
    items: list[BoardItem]
    next_steps: str = Field(description="理事会で固めた後の流れ（改定案の修正、住民説明会、総会の議案と決議の種類）。2〜4文")
    notes: list[str] = Field(default_factory=list, description="改定案には含まれていないが、あわせて検討するとよい点（議題にはしない）。各1〜2文")


SYSTEM = """あなたは、マンション管理組合の理事会（規約見直し委員会）が規約の改定案を検討するための資料を書くアシスタントです。
読み手は理事・委員で、法律の専門家ではありません。

書き方:
- です・ます調。簡潔に。専門用語は最初に出たところで（ ）で短く説明する
- 改定案を議題にまとめる。関連する改定は1つの議題にまとめる。議題は段（tier）ごとに、重要な順に並べる。全体で12個まで
- 段の意味：
  ・「法律の改正に合わせる変更」…改正された法律に合わせるため必ず必要な変更（アプリが改定案の必須の論点から決め直す）
  ・「暮らしや運営に関わる変更」…法律上は必須ではなく、組合が採用するか・どう書くかを決められる変更
  ・「古い規定や表現の整理」…参照する条の番号の誤りや古い用語を整えるだけで、内容が変わらないもの
- すべての改定の ref が、いずれかの議題の articles に入るようにする。改定案に含まれていない条についての提案は議題にせず notes に書く
- ②の議題では、判断に必要な材料（利点・注意点・暮らしへの影響）を公平に書く。どちらかに誘導しない
- 事実を誇張しない。「無効です」と断定せず「法律と食い違い、効力を失うおそれがあります」のように書く
- 専門家への相談を一律に勧めない
"""


def build_prompt(draft: Draft, info: dict) -> str:
    today = datetime.now(JST).date()
    amendments = [
        {"ref": ref_name(a), "document": a.document,
         **{k: v for k, v in a.to_dict().items() if k in ("kind", "caption", "reason", "finding_refs", "choices", "law_basis", "standard_basis")}}
        for a in draft.amendments
    ]
    return "\n".join([
        "次の管理規約（細則を含む）の改定案について、理事会で検討するための資料を作ってください。",
        f"基準日：{today.year}年{today.month}月{today.day}日"
        + ("（改正区分所有法は2026年4月1日に施行済み）" if today >= ENFORCED else ""),
        "規約の改定は総会の特別決議、細則（document が「規約」以外）の改定は普通決議で決める。",
        "",
        "## マンションの基本情報",
        *[f"- {k}：{v}" for k, v in info.items()],
        "",
        "## 改定案（ref ごと。reason は担当者向けの理由）",
        json.dumps(amendments, ensure_ascii=False),
        "",
        "## 担当者への申し送り（参考）",
        draft.notes,
    ])


def required_refs(draft: Draft) -> set[str]:
    from core.topics import REQUIRED_TOPIC_IDS

    return {_ref_key(ref_name(a)) for a in draft.amendments if set(a.finding_refs) & set(REQUIRED_TOPIC_IDS)}


def fix_tiers(paper: BoardPaper, draft: Draft) -> None:
    """①かどうかを改定案の必須の論点から決め直し、段の順に並べる。"""
    # 関係する改定がない議題は判断のしようがないので、参考（notes）に移す
    for item in [it for it in paper.items if not it.articles]:
        paper.notes.append(f"{item.title}：{item.summary}")
        paper.items.remove(item)
    req = required_refs(draft)
    for item in paper.items:
        if any(_ref_key(x) in req for x in item.articles):
            item.tier = TIERS[0]
        elif item.tier == TIERS[0]:
            item.tier = TIERS[1]
        if item.tier != TIERS[1]:
            item.options = []
    order = {t: i for i, t in enumerate(TIERS)}
    paper.items.sort(key=lambda it: order[it.tier])


def coverage(paper: BoardPaper, draft: Draft) -> list[str]:
    """どの議題にも入っていない改定の ref。"""
    covered = {_ref_key(x) for it in paper.items for x in it.articles}
    return [ref_name(a) for a in draft.amendments if _ref_key(ref_name(a)) not in covered]


def generate(draft: Draft, info: dict, effort: str = "medium") -> tuple[BoardPaper, dict]:
    c = client()
    with c.beta.messages.stream(
        model=MODEL,
        max_tokens=32000,
        system=SYSTEM,
        output_config={"effort": effort},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_format=BoardPaper,
        messages=[{"role": "user", "content": build_prompt(draft, info)}],
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason == "refusal" or message.parsed_output is None:
        raise RuntimeError(f"検討資料を作れませんでした（stop_reason={message.stop_reason}）")
    paper = message.parsed_output
    fix_tiers(paper, draft)
    missing = coverage(paper, draft)
    if missing:  # 取りこぼした改定は「暮らしや運営に関わる変更」の議題として補う（判断の機会をなくさない）
        paper.items.append(BoardItem(
            tier=TIERS[1], title="その他の改定（資料の本文で取り上げていないもの）", articles=missing,
            summary="資料の本文で取り上げていない改定です。新旧対照表で内容を確認してください。",
            points=["新旧対照表の該当箇所を読み、採用するかを判断してください。"], options=[], questions=[]))
        fix_tiers(paper, draft)
    return paper, (message.usage.model_dump() if message.usage else {})


# ---- 判断の記録 ----

def default_decisions(paper: BoardPaper) -> dict[str, dict]:
    return {str(i): {"decision": "", "note": "", "choice": ""} for i, _ in enumerate(paper.items)}


def choice_points(paper: BoardPaper, draft: Draft | None) -> dict[int, list[dict]]:
    """議題ごとの、組合が選ぶ必要がある点（〔選択〕）。AI に任せず、改定案の choices から決める。

    ①②③のどの段の議題でも、〔選択〕を含む改定があれば選ぶ点として示す。
    """
    if draft is None:
        return {}
    by_key = {_ref_key(ref_name(a)): a for a in draft.amendments}
    out: dict[int, list[dict]] = {}
    for i, it in enumerate(paper.items):
        pts = []
        for x in it.articles:
            a = by_key.get(_ref_key(x))
            if a is None:
                continue
            for c in a.choices or []:
                if c.get("options"):
                    pts.append({"ref": ref_name(a), "caption": a.caption, "point": c.get("point", ""),
                                "options": list(c["options"]), "note": c.get("note", "")})
            if CHOICE_MARK in a.text and not a.choices:
                pts.append({"ref": ref_name(a), "caption": a.caption, "point": "〔選択〕の箇所", "options": [], "note": ""})
        if pts:
            out[i] = pts
    return out


def remaining_choices(draft: Draft) -> list[str]:
    """改定案の本文に〔選択〕が残っている改定（住民向け説明の前に、理事会で選んで作り直す）。"""
    return [ref_name(a) for a in draft.amendments if CHOICE_MARK in a.text]


def picked_text(points: list[dict], picked: dict) -> str:
    """選んだ案を1行にする（例：「第33条 届出の方法：（イ）書面又は電磁的方法」）。"""
    parts = []
    for j, p in enumerate(points):
        v = (picked or {}).get(str(j), "")
        if v:
            parts.append(f"{p['ref']} {p['point']}：{v}")
    return "／".join(parts)


def status(paper: BoardPaper, decisions: dict[str, dict], points: dict[int, list[dict]] | None = None) -> dict:
    """判断が済んだか、改定案の作り直しが要るかを返す。

    〔選択〕のある議題は、見送り以外なら案をすべて選ぶまで判断済みにしない。案を選んだら作り直しが要る。
    """
    points = points or {}
    undecided, redraft, skipped, needs_choice = [], [], [], []
    for i, it in enumerate(paper.items):
        d = decisions.get(str(i), {})
        pts = points.get(i, [])
        picked = [v for v in (d.get("picked") or {}).values() if v]
        if d.get("decision") not in DECISIONS[it.tier]:
            undecided.append(it.title)
        elif pts and d["decision"] != "見送り" and len(picked) < len(pts):
            undecided.append(it.title)
            needs_choice.append(it.title)
        elif d["decision"] in NEEDS_REDRAFT or (pts and picked and d["decision"] != "見送り"):
            redraft.append(it.title)
        elif d["decision"] == "見送り":
            skipped.append(it.title)
    return {"undecided": undecided, "redraft": redraft, "skipped": skipped, "needs_choice": needs_choice,
            "done": not undecided}


def skipped_refs(paper: BoardPaper, decisions: dict[str, dict]) -> set[str]:
    return {_ref_key(x) for i, it in enumerate(paper.items)
            if decisions.get(str(i), {}).get("decision") == "見送り" for x in it.articles}


def apply_to_draft(draft: Draft, paper: BoardPaper, decisions: dict[str, dict]) -> Draft:
    """見送りにした改定を除いた改定案を返す（住民向け説明に使う）。"""
    skip = skipped_refs(paper, decisions)
    return Draft(amendments=[a for a in draft.amendments if _ref_key(ref_name(a)) not in skip], notes=draft.notes)


def decisions_text(paper: BoardPaper, decisions: dict[str, dict]) -> str:
    """理事会の判断を文章にする（改定案の作り直しと住民向け説明の作成でAIに渡す）。"""
    lines = []
    for i, it in enumerate(paper.items):
        d = decisions.get(str(i), {})
        if not d.get("decision"):
            continue
        line = f"- 【{it.tier}】{it.title}（{'、'.join(it.articles)}）：{d['decision']}"
        if d.get("choice"):
            line += f"／選んだ案：{d['choice']}"
        if d.get("note"):
            line += f"／理事会のメモ：{d['note']}"
        lines.append(line)
    return "\n".join(lines)


def to_html(paper: BoardPaper, decisions: dict[str, dict] | None = None, name: str = "",
            points: dict[int, list[dict]] | None = None) -> str:
    decisions = decisions or {}
    points = points or {}

    def choice_box(pts: list[dict], picked: dict) -> str:
        if not pts:
            return ""
        rows = []
        for j, p in enumerate(pts):
            mine = (picked or {}).get(str(j), "")
            opts = "".join(f"<li>{'☑' if o == mine else '□'} {html.escape(o)}</li>" for o in p["options"]) \
                or f"<li>{'☑ ' + html.escape(mine) if mine else '□ ＿＿＿＿＿＿＿＿'}</li>"
            note = f'<div class="cnote">{html.escape(p["note"])}</div>' if p.get("note") else ""
            rows.append(f'<div class="cpoint"><b>{html.escape(p["ref"])}（{html.escape(p["caption"])}）：{html.escape(p["point"])}</b><ul>{opts}</ul>{note}</div>')
        return '<div class="choose"><h4>選ぶ必要があります（〔選択〕）</h4>' + "".join(rows) + "</div>"

    def li(xs):
        return "".join(f"<li>{html.escape(x)}</li>" for x in xs)

    parts, current = [], None
    for i, it in enumerate(paper.items):
        if it.tier != current:
            current = it.tier
            n = TIERS.index(it.tier)
            task, guide = TIER_TASK[it.tier]
            parts.append(f'<div class="tier tier{n + 1}"><h2>{"①②③"[n]} {html.escape(it.tier)}：<u>{task}</u></h2><p>{html.escape(guide)}</p></div>')
        d = decisions.get(str(i), {})
        choices = "　".join(f"□ {c}" for c in DECISIONS[it.tier])
        recorded = (f'<p class="rec">理事会の判断：<b>{html.escape(d["decision"])}</b>'
                    + (f"／選んだ案：{html.escape(d['choice'])}" if d.get("choice") else "")
                    + (f"／メモ：{html.escape(d['note'])}" if d.get("note") else "") + "</p>") if d.get("decision") else ""
        parts.append(f"""<section class="item">
<h3>{i + 1}. {html.escape(it.title)}</h3>
<p class="arts">関係する条：{html.escape('、'.join(it.articles))}</p>
<p>{html.escape(it.summary)}</p>
<h4>{TIER_TASK[it.tier][0].replace('する', '')}のポイント</h4><ul>{li(it.points)}</ul>
{('<h4>選べる案</h4><ul>' + li(it.options) + '</ul>') if it.options else ''}
{choice_box(points.get(i, []), d.get("picked") or {})}
{('<h4>想定される質問</h4><ul>' + li(it.questions) + '</ul>') if it.questions else ''}
<p class="decide">判断：{choices}　メモ：＿＿＿＿＿＿＿＿＿＿</p>{recorded}
</section>""")
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(paper.title)}</title>
<style>
body {{ font-family: "Hiragino Sans", "Noto Sans JP", "Yu Gothic", sans-serif; max-width: 820px; margin: 24px auto; padding: 0 16px; line-height: 1.8; color: #1f2328; }}
h1 {{ font-size: 1.4rem; border-bottom: 3px solid #1f5fae; padding-bottom: 6px; }}
.tier {{ margin-top: 2em; padding: 6px 14px; border-radius: 8px; }} .tier h2 {{ margin: .3em 0 .1em; font-size: 1.15rem; }} .tier p {{ margin: 0 0 .4em; font-size: .92rem; }}
.tier1 {{ background: #fde8e7; }} .tier2 {{ background: #e8eef7; }} .tier3 {{ background: #f1f3f5; }}
.item {{ border-top: 1px solid #d6dbe1; padding-top: 4px; }} h3 {{ font-size: 1.05rem; margin: 1em 0 .2em; }}
h4 {{ font-size: .95rem; color: #1f5fae; margin: .6em 0 .1em; }} ul {{ margin: .2em 0; }}
.arts {{ font-size: .82rem; color: #5b636e; margin: 0; }}
.decide {{ font-size: .9rem; background: #f7f8fa; padding: 4px 8px; border-radius: 4px; }}
.rec {{ font-size: .9rem; color: #0b6b2b; }}
.choose {{ border: 1.5px dashed #b54708; border-radius: 6px; padding: 4px 12px; margin: .6em 0; }} .choose h4 {{ color: #93370d; }}
.choose ul {{ list-style: none; padding-left: .6em; }} .cnote {{ font-size: .85rem; color: #5b636e; }}
.note {{ font-size: .85rem; color: #5b636e; border-top: 1px solid #d6dbe1; margin-top: 2em; padding-top: 8px; }}
@media print {{ body {{ margin: 0; font-size: 10.5pt; }} }}
</style></head><body>
<h1>{html.escape(paper.title)}</h1>
{('<p class="arts">' + html.escape(name) + '</p>') if name else ''}
<p>{html.escape(paper.intro)}</p>
{''.join(parts)}
{('<h2>参考：今回の改定案に含まれていない点</h2><ul>' + li(paper.notes) + '</ul>') if paper.notes else ''}
<h2>このあとの流れ</h2><p>{html.escape(paper.next_steps)}</p>
<p class="note">{DISCLAIMER}　改定案の条文そのものは「新旧対照表」を見てください。</p>
</body></html>
"""
