"""エージェントのカスタムツール（アプリ側で実行する）。

規約の本文は、エージェントが必要な条だけをこのツールで受け取る。
規約全体を Files API に上げないので、手元から出るのは処理に必要な範囲に限られる。
"""

from __future__ import annotations

import json

from core.findings import FINDING_SCHEMA, Finding, validate
from core.model import Kiyaku
from core.sources import law, normalize_article_ref, standard

MAX_ITEMS = 20

TOOL_DEFS = [
    {
        "type": "custom",
        "name": "list_articles",
        "description": "現行規約の条の一覧（条番号・見出し・章）を返す。最初に呼んで、規約の全体像をつかむ。",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "type": "custom",
        "name": "get_articles",
        "description": "現行規約の条の本文を返す。条番号は「第47条」「47」「第24条の2」のどれでもよい。一度に20条まで。",
        "input_schema": {
            "type": "object",
            "properties": {"articles": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_ITEMS}},
            "required": ["articles"],
            "additionalProperties": False,
        },
    },
    {
        "type": "custom",
        "name": "get_standard_articles",
        "description": "マンション標準管理規約（令和7年10月改正・単棟型）の条の本文を返す。選択式の規定は（ア）（イ）の両案を返す。一度に20条まで。",
        "input_schema": {
            "type": "object",
            "properties": {"articles": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_ITEMS}},
            "required": ["articles"],
            "additionalProperties": False,
        },
    },
    {
        "type": "custom",
        "name": "get_law_articles",
        "description": "建物の区分所有等に関する法律（区分所有法）の、2026年4月1日施行時点（令和7年改正後）の条文を返す。条番号は「第31条」「31」「6の2」など。一度に20条まで。",
        "input_schema": {
            "type": "object",
            "properties": {"articles": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_ITEMS}},
            "required": ["articles"],
            "additionalProperties": False,
        },
    },
    {
        "type": "custom",
        "name": "record_findings",
        "description": (
            "改正対応が必要な箇所（指摘）を記録する。アプリが根拠と引用を検証し、受け付けた指摘と、"
            "受け付けなかった指摘の理由を返す。受け付けられなかった指摘は、理由に従って直して送り直す。"
            "根拠を示せない指摘は送らない。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {"findings": {"type": "array", "items": FINDING_SCHEMA, "maxItems": MAX_ITEMS}},
            "required": ["findings"],
            "additionalProperties": False,
        },
    },
]


class ToolHandler:
    """1回のレビューで使うツールの実行役。受け付けた指摘をためておく。"""

    def __init__(self, kiyaku: Kiyaku):
        self.kiyaku = kiyaku
        self.findings: list[Finding] = []
        self.rejected: list[dict] = []
        self.calls: list[str] = []

    def run(self, name: str, tool_input: dict) -> str:
        self.calls.append(name)
        try:
            fn = getattr(self, f"_{name}")
        except AttributeError:
            return f"不明なツールです: {name}"
        return fn(**tool_input)

    def _list_articles(self) -> str:
        rows = [{"条": a.label + (f"（{a.variant}案）" if a.variant else ""), "見出し": a.caption, "章": a.chapter}
                for a in self.kiyaku.articles]
        return json.dumps({"条の数": len(rows), "条": rows}, ensure_ascii=False)

    def _get_from(self, source: Kiyaku, refs: list[str], name: str) -> str:
        out = []
        for ref in refs[:MAX_ITEMS]:
            number = normalize_article_ref(ref)
            found = [a for a in source.articles if a.number == number]
            if not found:
                out.append(f"【{ref}】{name}にこの条はありません。")
            for a in found:
                head = f"【{a.label}" + (f"（{a.variant}案）" if a.variant else "") + "】"
                note = f"\n{a.note}" if a.note else ""
                out.append(head + note + "\n" + a.text())
        return "\n\n".join(out)

    def _get_articles(self, articles: list[str]) -> str:
        return self._get_from(self.kiyaku, articles, "現行規約")

    def _get_standard_articles(self, articles: list[str]) -> str:
        return self._get_from(standard(), articles, "標準管理規約")

    def _get_law_articles(self, articles: list[str]) -> str:
        out = []
        for ref in articles[:MAX_ITEMS]:
            number = normalize_article_ref(ref)
            text = law().get(number)
            out.append(text if text else f"【{ref}】区分所有法にこの条はありません。")
        return "\n\n".join(out)

    def _record_findings(self, findings: list[dict]) -> str:
        accepted, rejected = [], []
        for i, raw in enumerate(findings[:MAX_ITEMS]):
            finding, messages = validate(raw, self.kiyaku)
            if finding:
                self.findings.append(finding)
                accepted.append({"番号": i, "条": finding.article, "論点": finding.topic_id, "区分": finding.category, "注意": messages})
            else:
                rejected.append({"番号": i, "条": raw.get("article"), "理由": messages})
                self.rejected.append({"finding": raw, "reasons": messages})
        return json.dumps({"受け付けた指摘": accepted, "受け付けなかった指摘": rejected,
                           "これまでに受け付けた件数": len(self.findings)}, ensure_ascii=False)
