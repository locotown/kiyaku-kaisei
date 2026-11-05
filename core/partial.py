"""理事会の判断を、改定案の対象の条だけに反映する（部分的な作り直し）。

全体の作り直し（core/drafting.py）は、規約を読み直し、採用した指摘すべての条を書き直して採点役が確かめるため、
20〜45分・数ドルかかる。理事会で〔選択〕の案を選んだだけ、メモで少し直すだけ、のときにはやりすぎなので、
変わった議題の条だけを AI に書き直させ（1回）、別の呼び出しで直した条と、その条を参照する条を確かめる（1回）。

書き直した結果は、アプリ側でも改定案全体として機械的に検査する（core.draft.check）。通らなければ反映しない。
確かめる役の指摘には根拠を付けさせ、根拠のない指摘は落とす（CLAUDE.md）。結果は総会提案の下書きで、法的助言ではない。
"""

from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel, Field

from core.config import MODEL, client
from core.draft import CHOICE_MARK, Amendment, Draft
from core.notes import cost_usd

WRITE_SYSTEM = f"""あなたは、マンションの管理規約の改定案を手直しする担当です。
理事会（法律の専門家ではない人たち）が改定案を検討し、議題ごとに判断しました。
その判断を、示された「書き直す条」だけに反映してください。

守ること：
- 理事会の判断で求められたところだけを変える。それ以外の文言・項の番号・書式は一字一句そのまま残す
- 「選んだ案」がある箇所は、その案に合わせて本文を確定させ、{CHOICE_MARK}の印を外し、決まった点を choices から除く
- 判断が「見送り」の議題に関わる条は、その議題の変更（その議題の論点に当たる部分）だけを取り除いて今の規約の文に戻し、ほかの議題の変更（特に法律の改正に合わせる変更）は残す
- 「理事会のメモ」で直し方が示されていれば、それに従う。メモがあいまいで直し方が決められないときは、文を変えずに summary にそう書く
- 条番号・文書（document）・改正／新設／削除の別は変えない。条番号の振り直しはしない
- 改正区分所有法（2026年4月施行）の強行規定に反する文にしない（例：緊急時の招集通知は1週間を下回らない、議案の要領はすべての議案で通知する、
  規約変更などの特別決議は組合員総数の過半数かつ議決権総数の過半数の出席で、出席組合員及びその議決権の各4分の3以上）。
  理事会の判断がこれに反する場合は、反しない形にとどめ、その理由を summary に書く
- text は「第○条　」で始め、第2項以降は「2　」、号は「一　」で始めて改行で区切る（今の改定案の文と同じ書式）
- reason は、専門家でない理事会の担当者に分かる平易な日本語で、理事会の判断も踏まえて2〜4文で書き直す
- law_basis・standard_basis・finding_refs は、変える理由がなければそのまま残す
- notes（担当者への申し送り）は、今の申し送りをもとに、理事会の判断で決まったこと（{CHOICE_MARK}で選んだ点など）を反映して書き直す。
  見出しの構成はそのまま。総会提案の下書きであり法的助言ではない旨を必ず残す
- 書き直した条を参照している他の条で、直す必要がありそうなものがあれば others に挙げる（他の条は書き直さない）"""

CHECK_SYSTEM = """あなたは、マンションの管理規約の改定案を確かめる採点役です。
理事会の判断を反映して、改定案の一部の条を AI が書き直しました。書き直した条を、次の観点で確かめてください。

1. 理事会の判断（選んだ案・メモ）が、本文（メモが理由の説明への指示なら、理由の説明）に正しく反映されているか。〔選択〕の印が残っていないか
   （委員会の記録がある条では、その記録にある委員会の意見や直した文は正しいものとして扱う）
2. 改正区分所有法（2026年4月施行）の強行規定に反していないか（決議の要件、招集通知の期間、議案の要領の通知 など）
3. 書き直す前の文から、判断と関係のない文言・数字・項の番号が変わっていないか
4. 書き直した条を参照している条（示したもの）と、条番号や言葉が食い違っていないか
5. 書式（「第○条　」、第2項以降は「2　」、号は「一　」）と、規約の言い回しが保たれているか

守ること：
- 気になる点には、必ず根拠（区分所有法第◯条、標準管理規約第◯条、理事会の判断、比べた条や元の文の該当部分）を書く。根拠を示せない点は書かない
- 与えられた資料にないことを推測で断定しない。分からないことは「要確認」として、何を確かめればよいかを書く
- 問題がなければ、問題なしと答える。無理に指摘を作らない
- 専門家でない人に分かる言葉で書く。結果は総会提案の下書きを見直すための参考であり、法的助言ではない"""


class ChoiceOut(BaseModel):
    point: str
    options: list[str]
    note: str = ""


class AmendmentOut(BaseModel):
    document: str = Field(description="今の改定案と同じ文書名")
    article: str = Field(description="今の改定案と同じ条番号")
    caption: str
    text: str = Field(description="理事会の判断を反映した条文全体")
    reason: str
    finding_refs: list[str]
    law_basis: list[str]
    standard_basis: list[str]
    choices: list[ChoiceOut] = Field(description="まだ決まっていない〔選択〕の点だけ。理事会で選んだ点は除く")


class OtherRef(BaseModel):
    ref: str = Field(description="直す必要がありそうな他の条（例：第45条）")
    why: str = Field(description="なぜ直す必要がありそうか。1文")


class RewriteOut(BaseModel):
    amendments: list[AmendmentOut]
    notes: str
    summary: str = Field(description="何をどう直したか（直せなかった点があればそれも）。専門家でない人向けに2〜4文")
    others: list[OtherRef] = Field(default_factory=list)


class Concern(BaseModel):
    kind: Literal["理事会の判断と合わない", "法律に合わないおそれ", "関係のない文言が変わった", "他の条と食い違う", "書式", "要確認"]
    ref: str = Field(description="どの条のことか")
    point: str = Field(description="気になる点。1〜2文")
    basis: str = Field(description="根拠。区分所有法第◯条、標準管理規約第◯条、理事会の判断、比べた文の該当部分")
    suggestion: str = Field(description="どう直すとよいか、または何を確かめればよいか。1〜2文")


class CheckOut(BaseModel):
    verdict: Literal["問題なし", "気になる点あり", "法律に合わないおそれ"]
    summary: str = Field(description="結論を1〜2文で")
    concerns: list[Concern]


def _key(document: str, article: str) -> tuple[str, str]:
    return (document or "規約", re.sub(r"[\s　]", "", article))


def referencing(draft: Draft, targets: list[Amendment]) -> list[Amendment]:
    """書き直す条の番号を本文で参照している、ほかの改定（同じ文書の中だけ）。"""
    keys = {_key(a.document, a.article) for a in targets}
    out = []
    for a in draft.amendments:
        if _key(a.document, a.article) in keys:
            continue
        body = re.sub(r"[\s　]", "", a.text)
        if any(doc == (a.document or "規約") and num in body for doc, num in keys):
            out.append(a)
    return out


def _am_json(a: Amendment) -> str:
    return json.dumps(a.to_dict(), ensure_ascii=False, indent=1)


def write_material(*, targets: list[dict], board: str, findings: list[dict], others: list[Amendment],
                   all_refs: list[str], notes: str) -> str:
    """書き直す AI に渡す材料。targets の各要素：{"amendment", "current", "basis", "human_note"}。"""
    parts = ["# 理事会の判断（書き直す条に関係するもの）", board or "（なし）", "# 書き直す条"]
    for t in targets:
        a: Amendment = t["amendment"]
        parts.append(f"## {a.document} {a.article}（{a.caption}）")
        parts.append("### 今の規約の文（改定前）\n" + (t["current"] or "（新しく設ける条）"))
        parts.append("### 今の改定案（この JSON を書き直す）\n" + _am_json(a))
        if t.get("human_note"):
            parts.append("### 委員会が手で直した文であること\nこの条の text は委員会が直した文です。委員会の言い回しは、理事会の判断で必要なところ以外は変えないでください。"
                         + f"委員会の補足：{t['human_note']}")
        for b in t.get("basis") or []:
            if b.get("text"):
                parts.append(f"### 根拠：{b['source']} {b['ref']}（{b.get('caption', '')}）\n{b['text']}")
    if findings:
        parts.append("# この条についての指摘（改正対応が必要な理由）")
        parts += [f"- [{f.get('topic_id', '')}・{f.get('category', '')}] {f.get('issue', '')} → 改定の方向：{f.get('proposal', '')}" for f in findings]
    if others:
        parts.append("# 書き直す条を参照している、ほかの改定（書き直さない。食い違いがあれば others に挙げる）")
        parts += [f"## {a.document} {a.article}（{a.caption}）\n{a.text}" for a in others]
    parts.append("# 改定案にあるすべての条\n" + "、".join(all_refs))
    parts.append("# 今の申し送り（notes）\n" + (notes or "（なし）"))
    return "\n\n".join(parts)


def check_material(*, board: str, changed: list[tuple[Amendment, Amendment]], others: list[Amendment],
                   human_notes: dict | None = None, currents: dict | None = None) -> str:
    """確かめる役に渡す材料。human_notes は 条 → 委員会の補足（委員会で直した文・写真の書き込みの反映の経緯）。"""
    parts = ["# 理事会の判断", board or "（なし）", "# 書き直した条"]
    for before, after in changed:
        parts.append(f"## {after.document} {after.article}（{after.caption}）")
        hn = (human_notes or {}).get(f"{after.document or '規約'}|{after.article}")
        if hn:
            parts.append("### 委員会の記録（この条は委員会が文を直している。理由の説明にある委員会の意見は、この記録に基づく）\n" + hn)
        cur = (currents or {}).get(f"{after.document or '規約'}|{after.article}")
        if cur is not None:  # 見送りで今の文に戻した箇所などを、今の規約の文と照らし合わせられるように
            parts.append("### 今の規約の文（改定前）\n" + (cur or "（新しく設ける条）"))
        parts.append("### 書き直す前\n" + before.text)
        parts.append("### 書き直した後（これを確かめる）\n" + after.text)
        if after.reason != before.reason:  # 理事会のメモが「理由の説明」への指示のこともあるので、理由も見せる
            parts.append("### 理由の説明（書き直す前）\n" + before.reason)
            parts.append("### 理由の説明（書き直した後）\n" + after.reason)
        if after.choices:
            parts.append("### まだ決まっていない選ぶ点\n" + "\n".join(f"- {c.get('point', '')}" for c in after.choices))
    if others:
        parts.append("# 書き直した条を参照している、ほかの改定")
        parts += [f"## {a.document} {a.article}（{a.caption}）\n{a.text}" for a in others]
    return "\n\n".join(parts)


def _call(system: str, material: str, ask: str, fmt, effort: str):
    c = client()
    with c.beta.messages.stream(
        model=MODEL,
        max_tokens=32000,
        system=system,
        output_config={"effort": effort},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_format=fmt,
        messages=[{"role": "user", "content": material + "\n\n" + ask}],
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason == "refusal" or message.parsed_output is None:
        raise RuntimeError(f"AI が結果を返しませんでした（stop_reason={message.stop_reason}）")
    return message.parsed_output, (message.usage.model_dump() if message.usage else {})


def rewrite(material: str, effort: str = "high") -> tuple[RewriteOut, float]:
    out, usage = _call(WRITE_SYSTEM, material, "理事会の判断を、書き直す条に反映してください。", RewriteOut, effort)
    return out, cost_usd(usage)


def check(material: str, effort: str = "medium") -> tuple[CheckOut, float]:
    out, usage = _call(CHECK_SYSTEM, material, "書き直した条を確かめてください。", CheckOut, effort)
    out.concerns = [x for x in out.concerns if x.basis.strip()]  # 根拠のない指摘は出さない
    if not out.concerns and out.verdict != "問題なし":
        out.verdict = "問題なし"
    return out, cost_usd(usage)


def merge(draft: Draft, out: RewriteOut, targets: list[Amendment]) -> tuple[Draft, list[tuple[Amendment, Amendment]]]:
    """書き直した条を改定案に入れる。条番号・文書・改正の別は元のまま（AI に変えさせない）。

    返すのは (新しい改定案, [(前, 後)])。対象でない条を AI が返しても使わない。
    """
    by_key = {_key(o.document, o.article): o for o in out.amendments}
    target_keys = {_key(a.document, a.article) for a in targets}
    changed, amendments = [], []
    for a in draft.amendments:
        k = _key(a.document, a.article)
        o = by_key.get(k) if k in target_keys else None
        if o is None:
            amendments.append(a)
            continue
        new = Amendment(kind=a.kind, article=a.article, before_article=a.before_article, caption=o.caption or a.caption,
                        text=o.text if a.kind != "削除" else a.text, reason=o.reason or a.reason,
                        finding_refs=o.finding_refs or a.finding_refs, law_basis=o.law_basis or a.law_basis,
                        standard_basis=o.standard_basis or a.standard_basis,  # 空で返しても根拠を落とさない
                        choices=[c.model_dump() for c in o.choices], document=a.document)
        amendments.append(new)
        if new.to_dict() != a.to_dict():
            changed.append((a, new))
    return Draft(amendments=amendments, notes=out.notes or draft.notes), changed


__all__ = ["CheckOut", "RewriteOut", "check", "check_material", "merge", "referencing", "rewrite", "write_material"]
