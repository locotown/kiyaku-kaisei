"""指摘（改正対応が必要な箇所）の形式と検証。

CLAUDE.md「根拠を示せない指摘は出さない」を、アプリ側で機械的に強制する。
エージェントが record_findings で送った指摘は、次を満たさない限り受け付けない。
  - 根拠（区分所有法の条文、または標準管理規約の条番号）が1つ以上ある
  - 根拠に挙げた条文が実在する（区分所有法：e-Gov 本文、標準管理規約：令和7年改正 単棟型）
  - 対象の条が現行規約に実在する（「規定なし」の指摘を除く）
  - 現行規約からの引用が、その条の本文に実際に含まれている
区分（必須・推奨）は、既知の論点では docs/DOMAIN.md（core/topics.py）の区分を使う。
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from core.model import Kiyaku
from core.sources import law, normalize_article_ref, standard
from core.topics import TOPIC_BY_ID

CATEGORIES = ("必須", "推奨", "参考")
WHERE = ("規約", "細則で対応可")
NO_ARTICLE = "規定なし"

FINDING_SCHEMA = {
    "type": "object",
    "properties": {
        "document": {"type": "string", "description": "対象の文書。規約本体なら「規約」、細則ならその題名（list_rules で確認）。新しい細則を作るべき場合は「規約」とし、where を「細則で対応可」にする"},
        "article": {"type": "string", "description": "対象となる条（例：「第47条」。項目形式の細則なら「2.」）。該当する規定がない場合は「規定なし」"},
        "topic_id": {"type": "string", "description": "改正論点のID（スキルの論点表の ID。例：「1-1」）。論点表にない場合は「other」"},
        "category": {"type": "string", "enum": list(CATEGORIES), "description": "必須／推奨／参考。既知の論点は論点表の区分が優先される"},
        "issue": {"type": "string", "description": "何が問題か。専門家でない担当者が読んで分かる日本語で、2〜3文"},
        "current_excerpt": {"type": "string", "description": "現行規約の該当箇所をそのまま引用（get_articles で取得した本文から一字一句そのまま。「規定なし」なら空文字）"},
        "law_basis": {"type": "array", "items": {"type": "string"}, "description": "根拠となる区分所有法の条文（例：「第31条第1項」）。改正後（2026年4月1日施行）の条文"},
        "standard_basis": {"type": "array", "items": {"type": "string"}, "description": "対応する標準管理規約（令和7年改正・単棟型）の条番号（例：「第47条第3項」）"},
        "where": {"type": "string", "enum": list(WHERE), "description": "規約の変更が必要か、使用細則などの細則で対応できるか"},
        "proposal": {"type": "string", "description": "改定の方向性（1〜2文）。条文案そのものは後の工程で作る"},
        "choice_needed": {"type": "boolean", "description": "標準管理規約に選択肢（（ア）（イ）など）があり、担当者が選ぶ必要がある場合 true"},
        "choice_note": {"type": "string", "description": "choice_needed が true のとき、選択肢と判断のポイント"},
    },
    "required": ["document", "article", "topic_id", "category", "issue", "current_excerpt", "law_basis", "standard_basis", "where", "proposal"],
    "additionalProperties": False,
}


@dataclass
class Finding:
    article: str
    topic_id: str
    category: str
    issue: str
    current_excerpt: str
    law_basis: list[str]
    standard_basis: list[str]
    where: str
    proposal: str
    choice_needed: bool = False
    choice_note: str = ""
    needs_confirmation: bool = False  # 論点表で「要確認」の論点
    warnings: list[str] = field(default_factory=list)
    document: str = "規約"  # 「規約」または細則の題名

    def to_dict(self) -> dict:
        return asdict(self)


def _squash(s: str) -> str:
    from core.split import normalize

    return re.sub(r"[\s　]", "", normalize(s))


def _law_exists(ref: str) -> bool:
    return normalize_article_ref(ref) in law()


def _standard_exists(ref: str) -> bool:
    return standard().find(normalize_article_ref(ref)) is not None


def validate(raw: dict, kiyaku) -> tuple[Finding | None, list[str]]:
    """指摘を検証する。受け付けられれば (Finding, 警告)、受け付けられなければ (None, 理由) を返す。

    kiyaku には規約本体（Kiyaku）か、規約本体と細則をまとめた Corpus を渡す。
    """
    from core.corpus import Corpus

    corpus = Corpus.of(kiyaku)
    errors: list[str] = []
    warnings: list[str] = []
    document = corpus.resolve(raw.get("document"))
    if document is None:
        errors.append(f"文書「{raw.get('document')}」が見つかりません。規約本体なら「規約」、細則は list_rules の題名を使ってください。")
        return None, errors
    law_basis = [x for x in raw.get("law_basis", []) if x.strip()]
    standard_basis = [x for x in raw.get("standard_basis", []) if x.strip()]

    if not law_basis and not standard_basis:
        errors.append("根拠（区分所有法の条文または標準管理規約の条番号）がありません。根拠を示せない指摘は出せません。")
    for ref in law_basis:
        if not _law_exists(ref):
            errors.append(f"区分所有法に「{ref}」が見つかりません。get_law_articles で条文を確認してください。")
    for ref in standard_basis:
        if not _standard_exists(ref):
            errors.append(f"標準管理規約（令和7年改正・単棟型）に「{ref}」が見つかりません。")

    article = raw.get("article", "").strip()
    excerpt = raw.get("current_excerpt", "").strip()
    if article != NO_ARTICLE:
        number = normalize_article_ref(article)
        found = corpus.find(document, number)
        if not found:
            where = "現行規約" if document == "規約" else f"「{document}」"
            errors.append(f"{where}に「{article}」が見つかりません。list_articles／list_rules で条番号を確認してください。")
        elif excerpt and not any(_squash(excerpt) in _squash(a.text()) for a in found):
            errors.append(f"引用が「{article}」の本文と一致しません。get_articles で取得した本文から一字一句そのまま引用してください。")
        elif not excerpt:
            errors.append("現行規約の該当箇所の引用（current_excerpt）がありません。")

    topic_id = raw.get("topic_id", "other")
    category = raw.get("category", "推奨")
    needs_confirmation = False
    if topic_id in TOPIC_BY_ID:
        topic_category = TOPIC_BY_ID[topic_id]["category"]
        needs_confirmation = topic_category == "要確認"
        fixed = "推奨" if needs_confirmation else topic_category
        if category != fixed:
            warnings.append(f"区分を論点表に合わせて「{category}」から「{fixed}」に変更しました。")
            category = fixed
    elif topic_id != "other":
        errors.append(f"論点ID「{topic_id}」は論点表にありません。論点表にない場合は「other」としてください。")
    elif category == "必須" and not law_basis:
        errors.append("論点表にない指摘を「必須」とするには、区分所有法の条文の根拠が必要です。")
    if category not in CATEGORIES:
        errors.append(f"区分「{category}」は使えません（必須／推奨／参考）。")
    if raw.get("where") not in WHERE:
        errors.append("where は「規約」か「細則で対応可」にしてください。")

    if errors:
        return None, errors
    return Finding(
        document=document,
        article=article,
        topic_id=topic_id,
        category=category,
        issue=raw["issue"],
        current_excerpt=excerpt,
        law_basis=law_basis,
        standard_basis=standard_basis,
        where=raw["where"],
        proposal=raw["proposal"],
        choice_needed=bool(raw.get("choice_needed", False)),
        choice_note=raw.get("choice_note", ""),
        needs_confirmation=needs_confirmation,
        warnings=warnings,
    ), warnings
