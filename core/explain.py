"""住民（区分所有者）向けの説明文を作る。

改定案を、専門家でない住民が読める言葉に書き換える。資料を取り寄せる必要がない変換作業なので、
Managed Agents ではなく Messages API の1回の呼び出し（構造化出力）で作る（docs/ARCHITECTURE.md）。
"""

from __future__ import annotations

import html
import json
import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from core.config import MODEL, client
from core.draft import Draft
from core.printstyle import PRINT_CSS, page_css, toolbar
from core.readability import JARGON
from core.review import ENFORCED, JST

TIERS = ["法律の改正に合わせる変更", "暮らしや運営に関わる変更", "古い規定や表現の整理"]
TIER_GUIDE = {
    "法律の改正に合わせる変更": "改正された法律と食い違わないよう、必ず必要な変更です。",
    "暮らしや運営に関わる変更": "法律上は必須ではなく、採用するか・どう書くかを組合で決められる変更です。",
    "古い規定や表現の整理": "参照する条の番号や言い回しをそろえるなど、内容は変わらない整理です。",
}

DISCLAIMER = "この資料は総会提案の下書きであり、法的助言ではありません。改正区分所有法に抵触しない範囲では、内容は各管理組合が自由に決められます。"


class ExplainItem(BaseModel):
    title: str = Field(description="住民向けの見出し。例：「総会での決め方が変わります」")
    articles: list[str] = Field(description="関係する条（例：「第47条」）")
    required: bool = Field(description="改正法への対応として必要な変更なら true（アプリ側で改定案の必須の論点から決め直す）")
    tier: Literal["法律の改正に合わせる変更", "暮らしや運営に関わる変更", "古い規定や表現の整理"] = Field(
        description="どの段に載せるか。参照先の直し・言い回しの統一・古い制度名の更新など、住民の暮らしや運営に実質的に関わらないものは「古い規定や表現の整理」")
    what: str = Field(description="何が変わるか。2〜4文")
    why: str = Field(description="なぜ変えるか。2〜3文")
    impact: str = Field(description="暮らしや手続きにどう関わるか。関わりが小さければそう書く。1〜3文")
    finding_refs: list[str] = Field(default_factory=list, description="この項目が扱う論点ID（改定案の finding_refs から。この項目の変更に当たるものだけ）")


class Explanation(BaseModel):
    title: str = Field(description="資料の題名。例：「管理規約の改正について（ご説明）」")
    intro: str = Field(description="冒頭のあいさつと背景（法律が変わったこと、なぜ見直すか）。3〜5文")
    items: list[ExplainItem]
    choices: list[str] = Field(description="皆さんのご意見を伺いたい点（組合が選ぶ事項）。1項目1〜2文")
    resolution: str = Field(description="総会でどのように決めるか（決議の要件）を平易に。2〜3文")
    closing: str = Field(description="結び（質問の受付など）。1〜2文")


SYSTEM = """あなたは、マンション管理組合の理事会が住民（区分所有者）に配る説明資料を書くアシスタントです。
読み手は法律の専門家ではなく、高齢の方も含みます。

書き方:
- です・ます調。1文は60字程度までを目安にし、長くなる文は分ける
- 法律用語はできるだけ日常の言葉に言い換える。使う場合は、最初に出たときに（ ）で短く説明する
  例：特別決議（規約の変更など大事なことを決めるときの、特に多くの賛成が必要な決め方）
- 次の用語は、資料の中で最初に使うところで必ず（ ）で説明する：{jargon}
- 条番号は本文では最小限にし、関係する条は articles に入れる
- 関連する改定は1つの項目にまとめる。項目は tier（段）ごとに、住民の関心が高い順（総会の決め方、お金、暮らしのルール、その他）に並べる
- 段は3つ：「法律の改正に合わせる変更」「暮らしや運営に関わる変更」「古い規定や表現の整理」。変更が多いときも、項目は全体で10個まで、「古い規定や表現の整理」は1〜2項目にまとめて短く書く
- すべての改定の条が、いずれかの項目の articles に入るようにする（取り上げない改定を作らない）
- 改正法への対応として必要な変更と、そうでない変更を区別する（required）
- 事実を誇張しない。「無効になります」と断定せず、「法律と食い違い、効力を失うおそれがあります」のように書く
- 組合が選ぶ事項（〔選択〕の箇所）は、勝手に決めず choices に書く
- 専門家への相談を一律に勧めない
""".format(jargon="、".join(JARGON))


def ref_name(a) -> str:
    """改定の参照名。規約本体は「第47条」、細則は「駐車場使用細則 第3条」（規約と細則の同じ番号を区別する）。"""
    if a.document == "規約":
        return a.article
    short = re.sub(r"^.*?マンション[\s　]*", "", a.document) or a.document  # 「○○マンション駐車場使用細則」→「駐車場使用細則」
    return f"{short} {a.article}"


def _ref_key(text: str) -> str:
    return re.sub(r"[\s　]", "", text)


def build_prompt(draft: Draft, info: dict, board: str = "", edits: dict | None = None) -> str:
    from core.board import committee_edits

    today = datetime.now(JST).date()
    human = committee_edits(draft, edits)
    amendments = [
        {"ref": ref_name(a), "document": a.document,
         **{k: v for k, v in a.to_dict().items() if k in ("kind", "caption", "reason", "finding_refs", "choices")},
         **({"committee_edit": human[ref_name(a)]} if ref_name(a) in human else {})}
        for a in draft.amendments
    ]
    has_rules = any(a.document != "規約" for a in draft.amendments)
    return "\n".join([
        "次の管理規約の改定案について、住民向けの説明資料の文章を作ってください。",
        f"基準日：{today.year}年{today.month}月{today.day}日"
        + ("（改正区分所有法は2026年4月1日に施行済み。規約の改正は改正法の要件で決議する）" if today >= ENFORCED else ""),
        "決議の要件（改正法）：組合員総数の過半数かつ議決権総数の過半数が出席し、出席者とその議決権の各4分の3以上の賛成。書面や代理人による投票も出席に数える。",
        *(["細則（document が「規約」以外）の改定は、総会の普通決議（出席者の議決権の過半数）で決める。規約の改定とは別の議案になることを resolution で説明する。"]
          if has_rules else []),
        "各項目の articles には、改定案の ref をそのまま書く（例：「第47条」「駐車場使用細則 第3条」）。",
        "各項目の finding_refs には、その項目が扱う論点IDだけを書く。法律で必ず必要な変更（必須の論点）と、組合で選べる変更を同じ項目にまとめない"
        "（1つの条に両方が入っていても、項目は論点ごとに分ける）。理事会の判断の【段】に合わせる。",
        "",
        "## マンションの基本情報",
        *[f"- {k}：{v}" for k, v in info.items()],
        "",
        "## 改定案（条ごと。reason は担当者向けの理由）",
        json.dumps(amendments, ensure_ascii=False),
        "",
        "## 担当者への申し送り（参考）",
        draft.notes,
        *(["", "## 理事会の判断（この判断に沿って説明する。選んだ案があればその案で説明し、ご意見を伺いたい点には残さない）",
            "理事会のメモは理事会の内部の記録。住民に伝えるべき内容（修正した理由など）だけを説明に使い、"
            "「次回確認する」「管理会社に聞く」などの理事会の段取りや宿題は書かない。", board]
          if board else []),
        *(["", "committee_edit がある条は、委員会が文を直した条。reason は直す前の文についての説明のことがあるので、"
            "committee_edit を踏まえ、「標準管理規約と同じ」「それ以外は変えていない」など直した文と食い違うことを書かない。"]
          if human else []),
    ])


def generate(draft: Draft, info: dict, effort: str = "medium", board: str = "", edits: dict | None = None) -> tuple[Explanation, dict]:
    """説明文を作る。(説明, 使用量) を返す。"""
    c = client()
    with c.beta.messages.stream(
        model=MODEL,
        max_tokens=32000,
        system=SYSTEM,
        output_config={"effort": effort},
        # 安全上の判定で断られた場合に、別のモデルで自動的にやり直す（Opus 5.5 の既定）
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_format=Explanation,
        messages=[{"role": "user", "content": build_prompt(draft, info, board, edits)}],
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason == "refusal" or message.parsed_output is None:
        raise RuntimeError(f"説明文を作れませんでした（stop_reason={message.stop_reason}）")
    usage = message.usage.model_dump() if message.usage else {}
    ex = message.parsed_output
    mark_required(ex, draft)
    return ex, usage


def mark_required(ex: Explanation, draft: Draft) -> None:
    """「法律の改正に合わせるための変更」かどうかは AI に任せず、改定案の必須の論点から決める。"""
    from core.topics import REQUIRED_TOPIC_IDS

    required_refs = {_ref_key(ref_name(a)) for a in draft.amendments if set(a.finding_refs) & set(REQUIRED_TOPIC_IDS)}
    for item in ex.items:
        # 項目が扱う論点が分かれば、その論点で決める（必須と推奨が同じ条に入っていても、推奨の項目を「必ず必要」にしない）
        if item.finding_refs:
            item.required = bool(set(item.finding_refs) & set(REQUIRED_TOPIC_IDS))
        else:
            item.required = any(_ref_key(x) in required_refs for x in item.articles)
        if item.required:
            item.tier = "法律の改正に合わせる変更"
        elif item.tier == "法律の改正に合わせる変更":
            item.tier = "暮らしや運営に関わる変更"
    order = {t: i for i, t in enumerate(TIERS)}
    ex.items.sort(key=lambda it: order[it.tier])


def coverage(ex: Explanation, draft: Draft) -> dict:
    """改定した条が、説明資料のどの項目で取り上げられているか。取り上げていない条も返す。"""

    where: dict[str, list[int]] = {}
    for i, it in enumerate(ex.items, 1):
        for x in it.articles:
            where.setdefault(_ref_key(x), []).append(i)
    rows, missing = [], []
    for a in draft.amendments:
        key = _ref_key(ref_name(a))
        rows.append({"article": ref_name(a), "caption": a.caption, "kind": a.kind, "document": a.document,
                     "items": where.get(key, [])})
        if key not in where:
            missing.append(ref_name(a))
    return {"rows": rows, "missing": missing}


def to_html(ex: Explanation, name: str = "", draft: Draft | None = None, ident: str = "") -> str:
    def p(text: str) -> str:
        return "".join(f"<p>{html.escape(x)}</p>" for x in text.split("\n") if x.strip())

    items = []
    current_tier = None
    for i, it in enumerate(ex.items, 1):
        if it.tier != current_tier:
            current_tier = it.tier
            n = TIERS.index(it.tier) + 1
            items.append(f'<div class="tier tier{n}"><h2>{"①②③"[n - 1]} {html.escape(it.tier)}</h2><p>{html.escape(TIER_GUIDE[it.tier])}</p></div>')
        tag = '<span class="tag must">法律の改正に合わせるための変更</span>' if it.required else '<span class="tag">組合で選べる変更</span>'
        items.append(f"""<section class="item">
<h3 class="title">{i}. {html.escape(it.title)}</h3>{tag}<span class="arts">関係する条：{html.escape('、'.join(it.articles))}</span>
<h4>何が変わるのか</h4>{p(it.what)}
<h4>なぜ変えるのか</h4>{p(it.why)}
<h4>暮らしや手続きへの影響</h4>{p(it.impact)}
</section>""")
    choices = "".join(f"<li>{html.escape(c)}</li>" for c in ex.choices)
    appendix = ""
    if draft is not None:
        from core.taisho import classify

        cov = coverage(ex, draft)
        trs = "".join(
            f"<tr><td>{html.escape(r['article'])}</td><td>{html.escape(r['caption'])}</td><td>{html.escape(r['kind'])}</td>"
            f"<td>{'法律の改正に合わせる' if classify(a)['is_required'] else '組合で選べる'}</td>"
            f"<td>{'特別決議' if a.document == '規約' else '普通決議'}</td>"
            f"<td>{'、'.join(str(x) for x in r['items']) or '本文では取り上げていません'}</td></tr>"
            for r, a in zip(cov["rows"], draft.amendments)
        )
        appendix = (f'<h2>付録：変更する条の一覧（{len(cov["rows"])}条）</h2>'
                    '<table class="list"><tr><th>条</th><th>見出し</th><th>種類</th><th>区分</th><th>決議</th><th>説明の項目</th></tr>'
                    f"{trs}</table>")
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(ex.title)}</title>
<style>{PRINT_CSS}{page_css(ex.title, ident=ident)}</style></head><body>
{toolbar("explain.docx", back_href="./#explain")}
<h1>{html.escape(ex.title)}</h1>
{('<p class="arts">' + html.escape(name) + '</p>') if name else ''}
{p(ex.intro)}
{''.join(items)}
{('<h2>皆さんのご意見を伺いたい点</h2><div class="box"><ul>' + choices + '</ul></div>') if ex.choices else ''}
<h2>総会での決め方</h2>{p(ex.resolution)}
{p(ex.closing)}
{appendix}
<p class="note">{DISCLAIMER}</p>
</body></html>
"""
