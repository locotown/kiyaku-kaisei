"""委員会・理事会で印刷した資料に書き込んだ内容を、スマホの写真から読み取って提案にする（書き込みの反映 第1段）。

流れ：写真 → 読み取り（画像を読める Claude。read_photo）→ 提案（AI を使わない。build_proposals）→ 人が確かめて反映（app/main.py）。
勝手には反映しない。決めるのは委員会・理事会。読み取りに自信のないもの・数字・条番号は、画面で目立たせる。

対象は「新旧対照表」（行の番号で条を特定する）と「理事会の検討資料」（議題の番号と、判断の□・〔選択〕の丸・メモ欄）。
"""

from __future__ import annotations

import base64
import io
import re
from typing import Literal

from pydantic import BaseModel, Field

from core.config import MODEL, client

MAX_SIDE = 1600  # スマホの写真は大きいので縮める（読み取りに十分で、費用が半分ほどになる）
# Claude Opus 5.5 の公開価格（ドル／100万トークン）。費用は概算として記録する
PRICE = {"input": 4.0, "output": 20.0, "cache_read": 0.4, "cache_write": 5.0}


class Annotation(BaseModel):
    target: Literal["新旧対照表の行", "検討資料の議題", "不明"] = Field(description="書き込みがどこにあるか")
    row: int | None = Field(description="新旧対照表の行の番号（印刷の「行12」の12）。分からなければ null")
    item: int | None = Field(description="検討資料の議題の番号（印刷の「3. 〜」の3）。分からなければ null")
    kind: Literal["文言の修正", "判断", "選択", "メモ・宿題", "読めない"] = Field(
        description="文言の修正：条文の語句を直す書き込み（取り消し線・挿入・書き換え）。判断：検討資料の「判断：□」の印。"
                    "選択：〔選択〕の案に付けた丸・印。メモ・宿題：それ以外の書き込み（質問、確認すること、意見）。読めない：判読できない")
    handwriting: str = Field(description="書いてある文字をそのまま（記号は ☑ ○ × → ／ などで表す）")
    new_text: str = Field(description="文言の修正のときだけ：書き込みを当てはめた、改定案の条の文の全体（印刷された改定案の文を元に、"
                                      "書き込みの部分だけを変える）。それ以外は空")
    decision: str = Field(description="判断のときだけ：印のある選択肢の文字を、印刷された選択肢のとおりに。それ以外は空")
    choice_point: int | None = Field(description="選択のときだけ：その議題の何番目の〔選択〕か（1から）。それ以外は null")
    choice_option: str = Field(description="選択のときだけ：丸の付いた案の文字を、印刷された案のとおりに。それ以外は空")
    confidence: Literal["高", "中", "低"] = Field(description="読み取りの確かさ")
    reason: str = Field(description="なぜそう読んだか（どの印・どの位置か）。1文")


class PhotoReading(BaseModel):
    document: Literal["新旧対照表", "理事会の検討資料", "その他・不明"]
    ident: str = Field(description="ページの右上の版の番号（「ID 0d9663-a1b2c3」の形）。読めなければ空")
    page: str = Field(description="ページの下のページ番号（「3 / 17」の形）。読めなければ空")
    annotations: list[Annotation] = Field(description="手書きの書き込み（印刷された文字は含めない）。書き込みがなければ空")
    note: str = Field(description="写真全体の注意（ぼやけている、端が切れている、など）。なければ空")


SYSTEM = """あなたは、マンション管理組合の規約見直し委員会が、印刷した資料に手で書き込んだ内容を読み取るアシスタントです。
写真には、このツールが印刷した資料（新旧対照表、または理事会の検討資料）が写っています。印刷された文字と、手書きの書き込み（多くは赤などの色のペン）を見分けて、手書きの書き込みだけを取り出してください。

- 書き込みがどこにあるかは、印刷された「行12」などの行の番号（新旧対照表）や、「3. 〜」の議題の番号（検討資料）で特定する
- 書いてあることを推測で補わない。読めない字は「読めない」とし、無理に読まない。数字・条番号は特に慎重に読み、自信がなければ確かさを「低」にする
- 文言の修正では、下の【印刷した資料の内容】にある改定案の文を元に、書き込みの部分だけを変えた文の全体を new_text に書く。書き込み以外の部分は一字も変えない
- 判断の印・〔選択〕の丸は、印刷された選択肢の文字のとおりに答える
- 余白の質問や「確認」などは、メモ・宿題として、書いてあるとおりに取り出す
"""


def preprocess(data: bytes) -> bytes:
    """写真を開き直して JPEG にする（向きを直し、長い辺を縮める）。画像として開けなければ ValueError。

    読み込んだファイルはそのまま使わず、開き直したものだけを保存・送信する（中身の分からないファイルを扱わない）。
    画像の部品（Pillow）がまだ入っていない環境では、JPEG・PNG を 4.5MB までそのまま使う（uv sync で入る）。
    """
    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError:
        if media_type(data) and len(data) <= 4_500_000:
            return data
        raise ValueError("画像として読めないファイルです（JPEG・PNG で 4.5MB まで）") from None

    try:
        im = Image.open(io.BytesIO(data))
        im = ImageOps.exif_transpose(im).convert("RGB")
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError("画像として読めないファイルです") from e
    im.thumbnail((MAX_SIDE, MAX_SIDE))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=85)
    return out.getvalue()


def media_type(data: bytes) -> str:
    """ファイルの先頭から、画像の種類を見分ける（JPEG・PNG 以外は空）。"""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    return ""


def taisho_context(draft, corpus) -> str:
    """新旧対照表の行（行の番号・条・見出し・改定案の文）。写真のページと照らし合わせるのに使う。"""
    from core.taisho import numbered, rows

    lines = ["【印刷した資料の内容：新旧対照表】（行の番号ごとに、改定案の条と文）"]
    for document, items in numbered(rows(draft, corpus)):
        for n, r in items:
            a = r["amendment"]
            label = a.label if hasattr(a, "label") else a.article
            head = f"行{n}：{'' if document == '規約' else document + ' '}{label}（{a.caption}）・{a.kind}"
            lines.append(head + "\n改定案の文：" + (a.text if a.kind != "削除" else "（削る）"))
    return "\n\n".join(lines)


def board_context(paper, points: dict) -> str:
    """検討資料の議題（番号・見出し・判断の選択肢・〔選択〕の案）。"""
    from core.board import DECISIONS

    lines = ["【印刷した資料の内容：理事会の検討資料】（議題の番号ごとに、判断の選択肢と〔選択〕の案）"]
    for i, it in enumerate(paper.items):
        lines.append(f"議題{i + 1}：{it.title}（{it.tier}）\n判断の選択肢：{' ／ '.join(DECISIONS[it.tier])}")
        for j, p in enumerate(points.get(i, []), 1):
            lines.append(f"  〔選択〕{j}：{p['ref']}（{p['caption']}）{p['point']}：案は {' ／ '.join(p['options']) or '（自由に記入）'}")
    return "\n".join(lines)


def read_photo(jpeg: bytes, context: str, effort: str = "high") -> tuple[PhotoReading, dict]:
    """写真1枚の書き込みを読み取る。資料の内容（context）は同じ回の写真で共通なので、キャッシュする。"""
    c = client()
    with c.beta.messages.stream(
        model=MODEL,
        max_tokens=16000,
        system=[{"type": "text", "text": SYSTEM + "\n\n" + context, "cache_control": {"type": "ephemeral"}}],
        output_config={"effort": effort},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_format=PhotoReading,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type(jpeg) or "image/jpeg",
                                         "data": base64.standard_b64encode(jpeg).decode()}},
            {"type": "text", "text": "この写真の手書きの書き込みを読み取ってください。"},
        ]}],
    ) as stream:
        message = stream.get_final_message()
    if message.stop_reason == "refusal" or message.parsed_output is None:
        raise RuntimeError(f"写真を読み取れませんでした（stop_reason={message.stop_reason}）")
    return message.parsed_output, (message.usage.model_dump() if message.usage else {})


def cost_usd(usage: dict) -> float:
    """使ったトークンから、費用の概算（ドル）。"""
    def n(k):
        return usage.get(k) or 0
    return round((n("input_tokens") * PRICE["input"] + n("output_tokens") * PRICE["output"]
                  + n("cache_read_input_tokens") * PRICE["cache_read"] + n("cache_creation_input_tokens") * PRICE["cache_write"]) / 1e6, 4)


def changes(current: str, proposed: str, ctx: int = 10) -> list[dict]:
    """変わるところだけを、前後の文脈つきで取り出す（長い条でも、どこが変わるかがすぐ分かるように）。

    返すのは [{"before": [(文字列, 変わったか)], "after": [...]}]。近い変更はまとめる。
    """
    import difflib
    import re as _re

    # 改行の形（\r\n・段落の間の空行）の違いを差分に出さない（変わらない行が差分に並んだ、という声から）
    def norm(t: str) -> str:
        return _re.sub(r"\n{2,}", "\n", (t or "").replace("\r\n", "\n").replace("\r", "\n")).strip()

    current, proposed = norm(current), norm(proposed)
    ops = [o for o in difflib.SequenceMatcher(None, current, proposed, autojunk=False).get_opcodes() if o[0] != "equal"]
    groups: list[list] = []
    for o in ops:
        if groups and o[1] - groups[-1][-1][2] <= ctx * 2:
            groups[-1].append(o)
        else:
            groups.append([o])
    out = []
    for g in groups:
        a0, a1 = max(0, g[0][1] - ctx), min(len(current), g[-1][2] + ctx)
        b0, b1 = max(0, g[0][3] - ctx), min(len(proposed), g[-1][4] + ctx)

        def parts(text, lo, hi, spans):
            res, pos = [], lo
            for s0, s1 in spans:
                if s0 > pos:
                    res.append((text[pos:s0], False))
                if s1 > s0:
                    res.append((text[s0:s1], True))
                pos = s1
            if hi > pos:
                res.append((text[pos:hi], False))
            return res
        out.append({"before": ("…" if a0 > 0 else "", parts(current, a0, a1, [(o[1], o[2]) for o in g]), "…" if a1 < len(current) else ""),
                    "after": ("…" if b0 > 0 else "", parts(proposed, b0, b1, [(o[3], o[4]) for o in g]), "…" if b1 < len(proposed) else "")})
    return out


NUMERIC = re.compile(r"[0-9０-９一二三四五六七八九十百]|条|項|号|日|週|月|年|分の")


def _needs_check(text: str, confidence: str) -> bool:
    """人が特に確かめる書き込み（読み取りに自信がない、または数字・条番号・期間を含む）。"""
    return confidence == "低" or bool(NUMERIC.search(text or ""))


def build_proposals(reading: PhotoReading, photo: int, *, draft=None, corpus=None, paper=None, points: dict | None = None,
                    board_decisions: dict | None = None) -> list[dict]:
    """読み取った書き込みを、反映の提案にする（AI を使わない）。当てはまる先がなければ「メモ・宿題」にする。"""
    from core.board import DECISIONS
    from core.taisho import numbered, rows

    points, board_decisions = points or {}, board_decisions or {}
    by_row = {}
    if draft is not None:
        for _document, items in numbered(rows(draft, corpus)):
            for n, r in items:
                by_row[n] = r["amendment"]
    out = []

    def add(kind: str, a: Annotation, where: str, **kw) -> None:
        out.append({"kind": kind, "photo": photo, "where": where, "handwriting": a.handwriting, "confidence": a.confidence,
                    "reason": a.reason, "check": _needs_check(a.handwriting + kw.get("proposed", ""), a.confidence),
                    "status": "未確認", **kw})

    for a in reading.annotations:
        if a.kind == "読めない":
            add("読めない", a, f"行{a.row}" if a.row else (f"議題{a.item}" if a.item else "場所不明"))
            continue
        if a.target == "新旧対照表の行" and a.row in by_row:
            am = by_row[a.row]
            label = am.label if hasattr(am, "label") else am.article
            where = f"行{a.row} {label}（{am.caption}）"
            if a.kind == "文言の修正" and a.new_text.strip() and a.new_text.strip() != am.text.strip():
                add("文言の修正", a, where, row=a.row, article=am.article, document=am.document,
                    current=am.text, proposed=a.new_text.strip())
            else:
                add("メモ・宿題", a, where, proposed=a.handwriting)
            continue
        if a.target == "検討資料の議題" and paper is not None and a.item and 1 <= a.item <= len(paper.items):
            i = a.item - 1
            it = paper.items[i]
            where = f"議題{a.item} {it.title}"
            d = board_decisions.get(str(i), {})
            if a.kind == "判断":
                options = DECISIONS[it.tier]
                picked = next((o for o in options if o == a.decision.strip()), None) or \
                    next((o for o in options if o and o in a.decision), None)
                if picked:
                    add("判断", a, where, item=i, current=d.get("decision", ""), proposed=picked)
                    continue
            if a.kind == "選択" and a.choice_point:
                pts = points.get(i, [])
                if 1 <= a.choice_point <= len(pts):
                    p = pts[a.choice_point - 1]
                    opt = a.choice_option.strip()
                    picked = next((o for o in p["options"] if o == opt), None) or next((o for o in p["options"] if opt and opt in o), None)
                    if picked or (opt and not p["options"]):
                        add("選択", a, f"{where}：〔選択〕{p['ref']} {p['point']}", item=i, point=a.choice_point - 1,
                            current=(d.get("picked") or {}).get(str(a.choice_point - 1), ""), proposed=picked or opt)
                        continue
            add("理事会のメモ", a, where, item=i, current=d.get("note", ""), proposed=a.handwriting)
            continue
        add("メモ・宿題", a, "場所不明", proposed=a.handwriting)
    for k, p in enumerate(out):
        p["id"] = f"{photo}-{k + 1}"
    return out
