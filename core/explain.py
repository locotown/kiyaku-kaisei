"""住民（区分所有者）向けの説明文を作る。

改定案を、専門家でない住民が読める言葉に書き換える。資料を取り寄せる必要がない変換作業なので、
Managed Agents ではなく Messages API の1回の呼び出し（構造化出力）で作る（docs/ARCHITECTURE.md）。
"""

from __future__ import annotations

import html
import json
from datetime import datetime

from pydantic import BaseModel, Field

from core.config import MODEL, client
from core.draft import Draft
from core.readability import JARGON
from core.review import ENFORCED, JST

DISCLAIMER = "この資料は総会提案の下書きであり、法的助言ではありません。改正区分所有法に抵触しない範囲では、内容は各管理組合が自由に決められます。"


class ExplainItem(BaseModel):
    title: str = Field(description="住民向けの見出し。例：「総会での決め方が変わります」")
    articles: list[str] = Field(description="関係する条（例：「第47条」）")
    required: bool = Field(description="改正法への対応として必要な変更なら true（アプリ側で改定案の必須の論点から決め直す）")
    what: str = Field(description="何が変わるか。2〜4文")
    why: str = Field(description="なぜ変えるか。2〜3文")
    impact: str = Field(description="暮らしや手続きにどう関わるか。関わりが小さければそう書く。1〜3文")


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
- 関連する改定は1つの項目にまとめ、住民の関心が高い順（総会の決め方、お金、暮らしのルール、その他）に並べる。項目は多くても8つまで
- 改正法への対応として必要な変更と、そうでない変更を区別する（required）
- 事実を誇張しない。「無効になります」と断定せず、「法律と食い違い、効力を失うおそれがあります」のように書く
- 組合が選ぶ事項（〔選択〕の箇所）は、勝手に決めず choices に書く
- 専門家への相談を一律に勧めない
""".format(jargon="、".join(JARGON))


def build_prompt(draft: Draft, info: dict) -> str:
    today = datetime.now(JST).date()
    amendments = [
        {k: v for k, v in a.to_dict().items() if k in ("kind", "article", "caption", "reason", "finding_refs", "choices")}
        for a in draft.amendments
    ]
    return "\n".join([
        "次の管理規約の改定案について、住民向けの説明資料の文章を作ってください。",
        f"基準日：{today.year}年{today.month}月{today.day}日"
        + ("（改正区分所有法は2026年4月1日に施行済み。規約の改正は改正法の要件で決議する）" if today >= ENFORCED else ""),
        "決議の要件（改正法）：組合員総数の過半数かつ議決権総数の過半数が出席し、出席者とその議決権の各4分の3以上の賛成。書面や代理人による投票も出席に数える。",
        "",
        "## マンションの基本情報",
        *[f"- {k}：{v}" for k, v in info.items()],
        "",
        "## 改定案（条ごと。reason は担当者向けの理由）",
        json.dumps(amendments, ensure_ascii=False),
        "",
        "## 担当者への申し送り（参考）",
        draft.notes,
    ])


def generate(draft: Draft, info: dict, effort: str = "medium") -> tuple[Explanation, dict]:
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
        messages=[{"role": "user", "content": build_prompt(draft, info)}],
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
    from core.sources import normalize_article_ref
    from core.topics import REQUIRED_TOPIC_IDS

    required_articles = {
        normalize_article_ref(a.article) for a in draft.amendments if set(a.finding_refs) & set(REQUIRED_TOPIC_IDS)
    }
    for item in ex.items:
        item.required = any(normalize_article_ref(x) in required_articles for x in item.articles)


def to_html(ex: Explanation, name: str = "") -> str:
    def p(text: str) -> str:
        return "".join(f"<p>{html.escape(x)}</p>" for x in text.split("\n") if x.strip())

    items = []
    for i, it in enumerate(ex.items, 1):
        tag = '<span class="tag must">法律の改正に合わせるための変更</span>' if it.required else '<span class="tag">より良い運営のための変更</span>'
        items.append(f"""<section class="item">
<h2>{i}. {html.escape(it.title)}</h2>{tag}<span class="arts">関係する条：{html.escape('、'.join(it.articles))}</span>
<h3>何が変わるのか</h3>{p(it.what)}
<h3>なぜ変えるのか</h3>{p(it.why)}
<h3>暮らしや手続きへの影響</h3>{p(it.impact)}
</section>""")
    choices = "".join(f"<li>{html.escape(c)}</li>" for c in ex.choices)
    return f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(ex.title)}</title>
<style>
body {{ font-family: "Hiragino Sans", "Noto Sans JP", "Yu Gothic", sans-serif; max-width: 760px; margin: 24px auto; padding: 0 16px; line-height: 1.9; color: #1f2328; font-size: 17px; }}
h1 {{ font-size: 1.45rem; border-bottom: 3px solid #1f5fae; padding-bottom: 6px; }}
h2 {{ font-size: 1.2rem; margin: 1.6em 0 .3em; }}
h3 {{ font-size: 1rem; color: #1f5fae; margin: .9em 0 .2em; }}
.item {{ border-top: 1px solid #d6dbe1; padding-top: 4px; }}
.tag {{ display: inline-block; font-size: .8rem; padding: 1px 8px; border-radius: 999px; background: #eef2f7; margin-right: 8px; }}
.tag.must {{ background: #fde8e7; color: #b42318; font-weight: 700; }}
.arts {{ font-size: .8rem; color: #5b636e; }}
.box {{ background: #f7f8fa; border-radius: 8px; padding: 10px 16px; }}
.note {{ font-size: .85rem; color: #5b636e; border-top: 1px solid #d6dbe1; margin-top: 2em; padding-top: 8px; }}
@media print {{ body {{ margin: 0; font-size: 12pt; }} }}
</style></head><body>
<h1>{html.escape(ex.title)}</h1>
{('<p class="arts">' + html.escape(name) + '</p>') if name else ''}
{p(ex.intro)}
{''.join(items)}
<h2>皆さんのご意見を伺いたい点</h2><div class="box"><ul>{choices}</ul></div>
<h2>総会での決め方</h2>{p(ex.resolution)}
{p(ex.closing)}
<p class="note">{DISCLAIMER}</p>
</body></html>
"""
