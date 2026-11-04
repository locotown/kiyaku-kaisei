"""委員会で直した条の文を、AI に確かめてもらう（押したときだけ動く。1条あたり数セント）。

人が直した文が、改正区分所有法・標準管理規約に照らして問題がないか、AI が作った元の文から意味が変わって
しまっていないかを、根拠付きで返す。根拠を示せない指摘は出さない（CLAUDE.md）。
結果は「総会提案の下書き」を見直すための参考で、法的助言ではない。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from core.config import MODEL, client
from core.notes import cost_usd  # 同じ価格表で概算する

SYSTEM = """あなたは、マンションの管理規約の改定を手伝う確認役です。
管理組合の委員会（法律の専門家ではない人たち）が、AI の作った改定案の条の文を手で直しました。
直した文を、次の観点で確かめ、専門家でない人に分かる言葉で返してください。

1. 改正区分所有法（2026年4月施行）に合わないおそれはないか（強行規定に反する、決議の要件を法律より緩くする など）
2. 改正後の標準管理規約（2025年10月）や、この改定で対応しようとしている論点から外れていないか
3. AI の元の文から、意味が変わったり、あいまいになったり、抜けたりしていないか（定足数・期間・数字・主語・条番号の参照）
4. 規約の他の条と言葉や参照が食い違っていないか（与えられた資料から分かる範囲で）

守ること：
- 気になる点には、必ず根拠（区分所有法第◯条、標準管理規約第◯条、または比べた条や元の文のどこか）を書く。根拠を示せない点は書かない
- 与えられた資料にないことを推測で断定しない。分からないことは「要確認」として、何を確かめればよいかを書く
- 委員会が意図して変えた点（言い回しを平易にした、組合の事情に合わせた）は、法律や標準管理規約に反しない限り問題にしない
- 問題がなければ、問題なしと答える。無理に指摘を作らない
- 結果は総会提案の下書きを見直すための参考であり、法的助言ではない"""


class EditConcern(BaseModel):
    kind: Literal["法律に合わないおそれ", "標準管理規約・論点から外れる", "意味が変わった・あいまい", "他の条と食い違う", "要確認"]
    point: str = Field(description="気になる点。専門家でない人に分かる言葉で1〜2文")
    basis: str = Field(description="根拠。区分所有法第◯条、標準管理規約第◯条、または比べた条や元の文の該当部分")
    suggestion: str = Field(description="どう直すとよいか、または何を確かめればよいか。1〜2文")


class EditReview(BaseModel):
    verdict: Literal["問題なし", "気になる点あり", "法律に合わないおそれ"]
    summary: str = Field(description="結論を1〜2文で")
    concerns: list[EditConcern]


def context(*, article: str, caption: str, current: str, original: str, edited: str, note: str,
            findings: list[dict], basis: list[dict]) -> str:
    """AI に渡す材料。現行の文、AI の元の文、委員会で直した文、関係する指摘、根拠の条文。"""
    parts = [f"# 確かめる条：{article}（{caption}）",
             "## 現行の規約の文", current or "（新しく設ける条）",
             "## AI が作った改定案の文（委員会が直す前）", original,
             "## 委員会で直した文（これを確かめる）", edited]
    if note:
        parts += ["## 委員会の補足（直した理由・経緯）", note]
    if findings:
        parts.append("## この条についての指摘（改正対応が必要な理由）")
        for f in findings:
            parts.append(f"- [{f.get('category', '')}] {f.get('issue', '')} → 改定の方向：{f.get('proposal', '')}")
    if basis:
        parts.append("## 根拠の条文")
        for b in basis:
            if b.get("text"):
                parts.append(f"### {b['source']} {b['ref']}（{b.get('caption', '')}）\n{b['text']}")
    return "\n\n".join(parts)


def review_edit(material: str, effort: str = "medium") -> tuple[EditReview, dict]:
    """直した条の文を確かめる。根拠のない指摘は落とす。"""
    c = client()
    with c.beta.messages.stream(
        model=MODEL,
        max_tokens=8000,
        system=SYSTEM,
        output_config={"effort": effort},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_format=EditReview,
        messages=[{"role": "user", "content": material + "\n\n委員会で直した文を確かめてください。"}],
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason == "refusal" or message.parsed_output is None:
        raise RuntimeError(f"確かめられませんでした（stop_reason={message.stop_reason}）")
    review = message.parsed_output
    review.concerns = [x for x in review.concerns if x.basis.strip()]
    if not review.concerns and review.verdict != "問題なし":
        review.verdict = "問題なし"
    return review, (message.usage.model_dump() if message.usage else {})


def label(edit: dict | None, text: str = "") -> str:
    """資料に出す印。直した文が確かめたときの文と同じときだけ「AI 確認済み」にする。"""
    if not edit:
        return ""
    r = edit.get("review") or {}
    if r.get("status") == "済み" and r.get("for_text") == (text or edit.get("text")):
        return f"委員会で直した文（AI 確認済み：{r.get('verdict', '')}）"
    return "委員会で直した文（AI の確認前）"


__all__ = ["EditConcern", "EditReview", "context", "cost_usd", "label", "review_edit"]
