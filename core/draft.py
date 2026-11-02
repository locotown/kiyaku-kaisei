"""改定案（条ごとの改正・新設・削除）の形式と検証。

エージェントは改定案を JSON で書き、/mnt/session/outputs/kaitei.json に保存する。
提出前に check_draft ツールで機械的な検査を受け、受け取ったアプリ側でも同じ検査をする。
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from core.findings import Finding
from core.model import Kiyaku
from core.sources import law, normalize_article_ref, standard

KINDS = ("改正", "新設", "削除")
CHOICE_MARK = "〔選択〕"

AMENDMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": list(KINDS)},
        "article": {"type": "string", "description": "改定後の条番号（例：「第47条」「第24条の2」）。削除なら削除する条"},
        "before_article": {"type": ["string", "null"], "description": "現行規約の条番号。新設なら null"},
        "caption": {"type": "string", "description": "見出し（括弧なし。例：「総会の会議及び議事」）"},
        "text": {"type": "string", "description": "改定後の条文全体。「第47条　」から始め、第2項以降は「2　」、号は「一　」で始めて改行で区切る。削除なら空"},
        "reason": {"type": "string", "description": "変更の理由（担当者向け、平易な日本語で2〜4文）"},
        "finding_refs": {"type": "array", "items": {"type": "string"}, "description": "対応する指摘の論点ID（例：「1-1」「1-2」）"},
        "law_basis": {"type": "array", "items": {"type": "string"}},
        "standard_basis": {"type": "array", "items": {"type": "string"}},
        "choices": {
            "type": "array",
            "description": "担当者が選ぶ必要がある点（選択式の規定など）。本文の該当箇所には〔選択〕を付ける",
            "items": {"type": "object", "properties": {"point": {"type": "string"}, "options": {"type": "array", "items": {"type": "string"}}, "note": {"type": "string"}},
                      "required": ["point", "options"]},
        },
    },
    "required": ["kind", "article", "before_article", "caption", "text", "reason", "finding_refs", "law_basis", "standard_basis"],
}

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "amendments": {"type": "array", "items": AMENDMENT_SCHEMA},
        "notes": {"type": "string", "description": "担当者への申し送り。「総会提案の下書きであり、法的助言ではない」旨を含める"},
    },
    "required": ["amendments", "notes"],
}


@dataclass
class Amendment:
    kind: str
    article: str
    before_article: str | None
    caption: str
    text: str
    reason: str
    finding_refs: list[str]
    law_basis: list[str]
    standard_basis: list[str]
    choices: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Draft:
    amendments: list[Amendment]
    notes: str

    def to_dict(self) -> dict:
        return {"amendments": [a.to_dict() for a in self.amendments], "notes": self.notes}


def _lead_number(text: str) -> str | None:
    m = re.match(r"^\s*第\s*([0-9０-９一二三四五六七八九十百]+)\s*条((?:\s*の\s*[0-9０-９一二三四五六七八九十]+)*)", text)
    return normalize_article_ref(m.group(0)) if m else None


def check(data: dict, kiyaku: Kiyaku, findings: list[Finding]) -> tuple[Draft | None, list[str], list[str]]:
    """改定案を検査する。(Draft または None, エラー, 注意) を返す。"""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict) or not isinstance(data.get("amendments"), list):
        return None, ["JSON の形が違います。{\"amendments\": [...], \"notes\": \"...\"} にしてください。"], []

    amendments: list[Amendment] = []
    covered: set[str] = set()
    for i, raw in enumerate(data["amendments"]):
        where = f"amendments[{i}]（{raw.get('article', '?')}）"
        missing = [k for k in AMENDMENT_SCHEMA["required"] if k not in raw]
        if missing:
            errors.append(f"{where}：項目が足りません：{', '.join(missing)}")
            continue
        kind = raw["kind"]
        if kind not in KINDS:
            errors.append(f"{where}：kind は 改正／新設／削除 のどれかにしてください。")
            continue
        number = normalize_article_ref(raw["article"])
        before = raw.get("before_article")
        if kind in ("改正", "削除"):
            if not before or not [a for a in kiyaku.articles if a.number == normalize_article_ref(before)]:
                errors.append(f"{where}：現行規約に before_article「{before}」がありません。")
        if kind == "新設":
            if before:
                errors.append(f"{where}：新設なら before_article は null にしてください。")
            if [a for a in kiyaku.articles if a.number == number]:
                errors.append(f"{where}：「{raw['article']}」は現行規約にすでにあります。新設するなら枝番（例：第24条の2）を使ってください。")
        if kind != "削除":
            lead = _lead_number(raw["text"])
            if lead != number:
                errors.append(f"{where}：text は「{raw['article']}　」から始めてください。")
        if not raw.get("law_basis") and not raw.get("standard_basis"):
            errors.append(f"{where}：根拠（law_basis か standard_basis）がありません。")
        for ref in raw.get("law_basis", []):
            if normalize_article_ref(ref) not in law():
                errors.append(f"{where}：区分所有法に「{ref}」がありません。")
        for ref in raw.get("standard_basis", []):
            if standard().find(normalize_article_ref(ref)) is None:
                errors.append(f"{where}：標準管理規約に「{ref}」がありません。")
        if raw.get("choices") and CHOICE_MARK not in raw["text"]:
            warnings.append(f"{where}：choices があるのに本文に{CHOICE_MARK}がありません。")
        covered.update(raw.get("finding_refs", []))
        amendments.append(Amendment(
            kind=kind, article=raw["article"], before_article=before, caption=raw.get("caption", ""),
            text=raw.get("text", ""), reason=raw["reason"], finding_refs=raw.get("finding_refs", []),
            law_basis=raw.get("law_basis", []), standard_basis=raw.get("standard_basis", []),
            choices=raw.get("choices", []) or [],
        ))

    required = sorted({f.topic_id for f in findings if f.category == "必須"})
    for topic in required:
        if topic not in covered:
            errors.append(f"必須の指摘（論点 {topic}）に対応する改定がありません。finding_refs に論点IDを入れてください。")
    keys = [normalize_article_ref(a.article) for a in amendments]
    dup = {k for k in keys if keys.count(k) > 1}
    if dup:
        errors.append(f"同じ条の改定が複数あります：{', '.join(sorted(dup))}。1つの条は1つの改定にまとめてください。")
    if "法的助言" not in (data.get("notes") or ""):
        warnings.append("notes に「総会提案の下書きであり、法的助言ではない」旨がありません。")

    if errors:
        return None, errors, warnings
    return Draft(amendments=amendments, notes=data.get("notes", "")), [], warnings


def parse_json(text: str) -> dict:
    return json.loads(text)
