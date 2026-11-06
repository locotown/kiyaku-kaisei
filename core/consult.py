"""ととのう規約に相談する（AI 相談）。

理事会・委員会の人が、改正区分所有法・標準管理規約について質問したり、住民向けのニュース原稿・議事録・説明文などの
文章を貼って確かめてもらったりする。答えは、改定案づくりと同じ資料（区分所有法の条文・標準管理規約・改正論点の一覧・
お使いの規約）を AI に引かせて作り、根拠（条番号）を付ける。根拠を確かめられない答えは「資料の外」に分け、断定しない（CLAUDE.md）。

戸数・定足数・賛成数などの数は AI に計算させない。マンションの基本情報（住戸の数・組合員の数・議決権の総数）から、
アプリが計算する（votes）。基本情報がなければ、AI は数を推測せず「基本情報が必要」と返し、画面が記入を促す。

貼った文は人名を伏せて送れる（mask_names）。伏せた名前は、答えを画面に出すときに戻す。
答えは総会提案の下書きを見直すための参考で、法的助言ではない。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from core.config import MODEL, client
from core.notes import cost_usd
from core.sources import law, normalize_article_ref, standard
from core.topics import TOPICS

MAX_ITEMS = 20
MAX_TURNS = 14

# ---- マンションの基本情報 ----------------------------------------------------------

VOTE_RULES = ("1戸1議決権", "専有面積の割合など", "分からない")

PROFILE_FIELDS = {
    "units": "住戸の数",
    "owners": "組合員（区分所有者）の数",
    "votes_total": "議決権の総数",
}


def clean_profile(raw: dict) -> dict:
    """フォームの値を、基本情報として保存する形にそろえる。数は正の整数だけを受け取る。"""
    def num(v):
        s = str(v or "").strip().translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        return int(s) if s.isdigit() and int(s) > 0 else None

    p = {"name": str(raw.get("name") or "").strip()[:60], "units": num(raw.get("units")),
         "owners": num(raw.get("owners")), "votes_total": num(raw.get("votes_total")),
         "vote_rule": raw.get("vote_rule") if raw.get("vote_rule") in VOTE_RULES else "分からない",
         "work_id": str(raw.get("work_id") or "").strip(), "note": str(raw.get("note") or "").strip()[:400]}
    if p["vote_rule"] == "1戸1議決権" and p["units"]:
        p["votes_total"] = p["units"]                        # 1戸1議決権なら、議決権の総数は住戸の数（前の数を残さない）
        if not p["owners"] or p["owners"] > p["units"]:      # 組合員は、1人で2戸以上持つ人がいれば住戸の数より少ない
            p["owners"] = p["units"]
    return p


def missing(profile: dict | None) -> list[str]:
    """数の計算に足りない基本情報（画面の言葉）。"""
    p = profile or {}
    return [label for key, label in PROFILE_FIELDS.items() if not p.get(key)]


def _majority(n: int) -> int:
    return n // 2 + 1


def _at_least(n: int, a: int, b: int) -> int:
    """n の a/b 以上になる最小の整数。"""
    return -(-n * a // b)


KINDS = {
    "普通決議": "役員の選任、管理費・修繕積立金の変更など（標準管理規約 第47条第1項・第2項）",
    "特別決議": "規約の変更、共用部分の大きな変更など（区分所有法 第31条第1項・第17条第1項、標準管理規約 第47条第3項）",
    "3分の2の決議": "瑕疵の除去・バリアフリー化のための共用部分の変更、大規模滅失の復旧（区分所有法 第17条第5項・第61条第5項、標準管理規約 第47条第4項）",
    "建替え決議": "建替え・建物更新・取壊し（区分所有法 第62条ほか、標準管理規約 第47条第5項。全員が母数）",
}


def votes(profile: dict | None, kind: str, present_owners: int | None = None, present_votes: int | None = None) -> dict:
    """定足数と、可決に必要な賛成の数（アプリが計算する）。基本情報が足りなければ need を返す。"""
    p = profile or {}
    need = missing(p)
    if kind not in KINDS:
        return {"error": f"kind は {list(KINDS)} のどれかです"}
    if need:
        return {"need": need, "message": "マンションの基本情報が足りないので計算できません。数を推測せず、基本情報が必要と答えてください。"}
    owners, total = p["owners"], p["votes_total"]
    out = {"決議の種類": kind, "対象": KINDS[kind], "組合員の数": owners, "議決権の総数": total,
           "前提": f"議決権の決め方：{p.get('vote_rule', '分からない')}。書面（議決権行使書）・代理人（委任状）・電磁的方法で議決権を行使した人も出席に数える（区分所有法 第39条第2項・第3項、標準管理規約 第47条第7項）"}
    if kind == "建替え決議":
        out["必要な賛成"] = {"原則（各5分の4以上）": {"組合員": _at_least(owners, 4, 5), "議決権": _at_least(total, 4, 5)},
                          "耐震性の不足など法律の事由があるとき（各4分の3以上）": {"組合員": _at_least(owners, 3, 4), "議決権": _at_least(total, 3, 4)}}
        out["定足数"] = "なし（出席者ではなく、組合員全員・議決権全体が母数）"
        return out
    if kind == "普通決議":
        out["定足数"] = {"議決権": _majority(total), "説明": "議決権総数の過半数（標準管理規約 第47条第1項。お使いの規約の定めも確認）"}
        rule = ("過半数", lambda n: _majority(n))
    else:
        out["定足数"] = {"組合員": _majority(owners), "議決権": _majority(total), "説明": "組合員の過半数、かつ議決権の過半数が出席"}
        rule = ("4分の3以上", lambda n: _at_least(n, 3, 4)) if kind == "特別決議" else ("3分の2以上", lambda n: _at_least(n, 2, 3))
    out["賛成の割合"] = "出席した" + ("組合員の議決権の" if kind == "普通決議" else "組合員とその議決権の各") + rule[0]
    cases = []
    if present_owners or present_votes:
        po, pv = present_owners or present_votes, present_votes or present_owners
        ok = (pv >= _majority(total)) if kind == "普通決議" else (po >= _majority(owners) and pv >= _majority(total))
        cases.append({"場合": f"出席 組合員{po}・議決権{pv}", "総会が成立するか": "成立" if ok else "定足数に足りない",
                      "必要な賛成": ({"議決権": rule[1](pv)} if kind == "普通決議" else {"組合員": rule[1](po), "議決権": rule[1](pv)})})
    qo, qv = _majority(owners), _majority(total)
    cases.append({"場合": "ちょうど定足数だけ出席したとき", "必要な賛成": ({"議決権": rule[1](qv)} if kind == "普通決議" else {"組合員": rule[1](qo), "議決権": rule[1](qv)})})
    cases.append({"場合": "全員が出席したとき", "必要な賛成": ({"議決権": rule[1](total)} if kind == "普通決議" else {"組合員": rule[1](owners), "議決権": rule[1](total)})})
    out["計算"] = cases
    if kind == "特別決議":
        out["改正前との比べ"] = {"改正前（2026年3月までに招集した総会）": f"組合員総数と議決権総数の各4分の3以上（組合員{_at_least(owners, 3, 4)}・議決権{_at_least(total, 3, 4)}の賛成）",
                             "改正後": "上の定足数を満たしたうえで、出席者の各4分の3以上"}
    return out


# ---- 人名を伏せる -------------------------------------------------------------------

_NAME = re.compile(r"([一-龥々ヶ]{1,4}|[ァ-ヴー]{2,8})(?=\s?(?:さん|氏|様|君|くん|先生|委員長|理事長|副理事長|理事|監事))")
# 「記録：中川」「講師：森田一郎（…）」「司会　山田」のように、役の後に書いた名前
_ROLE_NAME = re.compile(r"(?:記録|講師|司会|議長|書記|作成|文責|担当|報告者|発言者|説明者|出席者?|欠席者?)\s*[:：　]\s*([^。\n]{1,80})")
_ROLE_PART = re.compile(r"^([一-龥々ヶ]{2,4})(?:[（(].*)?$")
_NOT_NAMES = {"管理員", "管理人", "住民", "皆", "組合員", "理事長", "理事", "監事", "委員長", "管理会社", "理事会", "未定", "全員", "なし", "区分所有者", "委員", "役員", "国内管理人", "専門家", "居住者", "管理会社", "理事会",
              "委員会", "同", "本", "各", "前", "新", "旧", "副", "現", "元", "当", "総", "全"}


def mask_names(text: str, extra: list[str] | None = None, more: list[str] | None = None) -> tuple[str, dict[str, str]]:
    """「◯◯さん」「◯◯氏」などの人名と、マンション名（extra）・ほかに伏せる語（more）を記号に置き換える。返すのは (伏せた文, 記号→元の語)。"""
    mapping: dict[str, str] = {}
    back: dict[str, str] = {}

    def token(word: str, prefix: str) -> str:
        if word not in back:
            n = sum(1 for k in mapping if k.startswith(prefix)) + 1
            tok = f"{prefix}{chr(ord('A') + n - 1) if n <= 26 else n}"
            back[word], mapping[tok] = tok, word
        return back[word]

    for words, prefix in ((extra, "マンション"), (more, "伏せた語")):   # 文にない語は記号にしない（伏せた語の数を正しく出す）
        for w in sorted({w.strip() for w in (words or []) if w and w.strip()}, key=len, reverse=True):
            if w in text:
                text = text.replace(w, token(w, prefix))

    found = {m.group(1) for m in _NAME.finditer(text) if m.group(1) not in _NOT_NAMES}
    for m in _ROLE_NAME.finditer(text):   # 役の後に「、」で並べた名前（敬称なし）
        for part in re.split(r"[、，,・／/]", m.group(1)):
            part = re.split(r"[:：　]", part.strip())[-1]   # 「、記録：中川」のように続けて書いた役
            mm = _ROLE_PART.match(re.sub(r"(氏|さん|様|先生)(?=[（(]|$)", "", part.strip()))
            if mm and mm.group(1) not in _NOT_NAMES:
                found.add(mm.group(1))
    for w in sorted(found, key=len, reverse=True):   # 長い名前から（「山本一郎」を「山本」より先に）
        text = text.replace(w, token(w, "人物"))
    return text, mapping


def unmask(value, mapping: dict[str, str]):
    """答えの中の記号を、元の語に戻す（文字列・リスト・辞書をたどる）。"""
    if not mapping:
        return value
    if isinstance(value, str):
        for tok in sorted(mapping, key=len, reverse=True):
            value = value.replace(tok, mapping[tok])
        return value
    if isinstance(value, list):
        return [unmask(v, mapping) for v in value]
    if isinstance(value, dict):
        return {k: unmask(v, mapping) for k, v in value.items()}
    return value


# ---- AI に渡す道具 -----------------------------------------------------------------

KNOWLEDGE = """# 改正の基本（ととのう規約の資料 docs/DOMAIN.md から）
- 改正区分所有法の施行日：2026年4月1日（令和7年改正）
- 令和7年改正法 附則第2条第3項：施行の際に効力を持つ規約で定めた事項のうち、新しい区分所有法に抵触するものは、施行日から効力を失う
  （規約を変えなくても、抵触する部分は法律が優先して適用される。ただし規約の文はそのまま残るので、見直しは必要）
- 附則第2条第2項：施行日より前に招集手続きが始まった集会には、従前の例による（2026年3月までに招集した総会は旧ルール）
- 区分所有法 第39条第2項・第3項：書面・代理人・電磁的方法で議決権を行使した人は、出席した区分所有者の数・議決権の数に算入する
- 改正前の規約変更の特別決議：区分所有者（組合員）総数と議決権総数の各4分の3以上（出席者ではなく全員が母数）
- 標準管理規約（令和7年10月改正）は国交省が示すモデル。各マンションの規約そのものではない。採り入れるかは組合が決める（法に抵触する部分を除く）
- 国交省の資料：【概要】令和7年マンション標準管理規約改正の概要、【スライド】説明資料、【留意点】規約改正の手続の留意点、【見え消し】改正箇所
  （【留意点】は、全員を母数にした古い規約の特別決議の定めは改正法に抵触し無効になるとしている）"""

TOOL_DEFS = [
    {"name": "get_law_articles",
     "description": "区分所有法（2026年4月1日施行時点、令和7年改正後）の条文を返す。条番号は「第31条」「31」「64の5」など。一度に20条まで。",
     "input_schema": {"type": "object", "properties": {"articles": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_ITEMS}},
                      "required": ["articles"], "additionalProperties": False}},
    {"name": "get_standard_articles",
     "description": "マンション標準管理規約（令和7年10月改正・単棟型）の条の本文（コメントを含む）を返す。一度に20条まで。",
     "input_schema": {"type": "object", "properties": {"articles": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_ITEMS}},
                      "required": ["articles"], "additionalProperties": False}},
    {"name": "list_topics",
     "description": "今回の改正で管理規約の見直しが論点になる項目の一覧（論点・必須か推奨か・関係する法律と標準管理規約の条・確かめる点）と、改正の基本（施行日・経過措置・出席の数え方）を返す。最初に呼ぶ。",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "get_building_info",
     "description": "このマンションの基本情報（住戸の数・組合員の数・議決権の総数・議決権の決め方）を返す。足りない項目も返す。",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "calc_votes",
     "description": "このマンションの基本情報から、総会の定足数と可決に必要な賛成の数を計算する。数は必ずこの道具で出し、自分で計算しない。"
                    "kind：普通決議／特別決議（規約の変更など）／3分の2の決議（瑕疵の除去・バリアフリー化・大規模滅失の復旧）／建替え決議。"
                    "出席の数が分かっていれば present_owners・present_votes に入れる。",
     "input_schema": {"type": "object", "properties": {
         "kind": {"type": "string", "enum": list(KINDS)},
         "present_owners": {"type": "integer"}, "present_votes": {"type": "integer"}},
         "required": ["kind"], "additionalProperties": False}},
    {"name": "list_articles",
     "description": "お使いの規約（現行規約）の条の一覧（条番号・見出し）と細則の名前を返す。照らす規約が選ばれていなければ、その旨を返す。",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "get_articles",
     "description": "お使いの規約（現行規約）の条の本文を返す。細則の条は rule に細則の名前を入れる。一度に20条まで。",
     "input_schema": {"type": "object", "properties": {"articles": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_ITEMS},
                                                       "rule": {"type": "string"}},
                      "required": ["articles"], "additionalProperties": False}},
]

SOURCES = ("区分所有法", "改正法附則", "標準管理規約", "国交省資料", "お使いの規約", "計算", "貼った文")
VERDICTS = ("正しい", "言い方に注意", "誤り", "資料の外", "体裁", "説明")

_BASIS = {"type": "object", "properties": {
    "source": {"type": "string", "enum": list(SOURCES)},
    "ref": {"type": "string", "description": "条番号（例：第31条第1項）、資料名（例：【留意点】）、計算の種類など"}},
    "required": ["source", "ref"], "additionalProperties": False}
_ITEM = {"type": "object", "properties": {
    "quote": {"type": "string", "description": "文章を確かめるとき：貼った文の該当部分をそのまま抜き出す（言い換えない）。質問の答えでは空"},
    "verdict": {"type": "string", "enum": list(VERDICTS)},
    "comment": {"type": "string", "description": "専門家でない人に分かる言葉で1〜4文"},
    "basis": {"type": "array", "items": _BASIS, "maxItems": 6},
    "suggestion": {"type": "string", "description": "直し案（そのまま使える文）、または何を確かめればよいか"}},
    "required": ["verdict", "comment", "basis"], "additionalProperties": False}

RECORD_DEF = {
    "name": "record_answer",
    "description": "答えを記録する。アプリが根拠を確かめ、受け付けたか、直す点を返す。受け付けられなければ、理由に従って直して送り直す。",
    "input_schema": {"type": "object", "properties": {
        "summary": {"type": "string", "description": "全体の答え・まとめ。専門家でない人に分かる言葉で2〜6文"},
        "items": {"type": "array", "items": _ITEM, "maxItems": 30},
        "need_info": {"type": "array", "items": {"type": "string", "enum": list(PROFILE_FIELDS.values())},
                      "description": "答えるのにマンションの基本情報が足りなかった項目"},
        "followups": {"type": "array", "items": {"type": "string"}, "maxItems": 3, "description": "続けて聞くとよい質問の例"}},
        "required": ["summary", "items"], "additionalProperties": False},
}

SYSTEM = f"""あなたは「ととのう規約」の相談役です。マンションの理事会・規約見直し委員会の人（法律の専門家ではない）からの
質問に答えたり、住民向けのニュース原稿・議事録・説明文などを確かめたりします。
対象は、2026年4月施行の改正区分所有法と、2025年10月改正のマンション標準管理規約、そしてその組合の管理規約です。

進め方：
1. 最初に list_topics を呼び、改正の論点と基本を確かめる
2. 答えに使う条は、必ず get_law_articles・get_standard_articles（照らす規約があれば get_articles）で本文を読んでから使う。覚えている内容で書かない
3. 戸数・定足数・賛成の数などの数は、calc_votes で計算する。自分で計算しない。基本情報が足りなければ数を推測せず、need_info に足りない項目を入れる
4. 最後に record_answer で答えを記録する。受け付けられなかったら、理由に従って直して送り直す

答え方：
- 「文章を確かめる」ときは、法律・規約・数に関わる記述を中心に、気になる記述ごとに1項目を作る。quote には貼った文の該当部分をそのまま抜き出す
  - 正しい：根拠で裏付けられる（大事な記述は、正しいものも挙げてよい）
  - 言い方に注意：大筋は合っているが、誤解を招く・不正確・範囲が広すぎる。直し案を付ける
  - 誤り：根拠と食い違う。直し案を付ける
  - 資料の外：ととのう規約の資料では確かめられない（統計の数字、当日の出来事など）。何で確かめればよいかを suggestion に書く。推測で正誤を断定しない
  - 体裁：見出しの重複、数字・日付の表記ゆれ、文章内の食い違い（根拠は「貼った文」でよい）
- 「質問する」ときは、summary に答えを書き、items に根拠のある説明（verdict は「説明」）と、資料で確かめられない点（「資料の外」）を分けて書く
- 正しい・言い方に注意・誤り・説明には、必ず根拠（basis）を付ける。区分所有法・標準管理規約・お使いの規約の条番号は、道具で読んだ条だけを書く
- 改正法附則（経過措置）は source を「改正法附則」・ref を「第2条第3項」のように、国交省の資料は「国交省資料」・ref を資料名に、
  calc_votes の結果は source を「計算」・ref を決議の種類（例：特別決議の定足数と賛成の数）にする。道具の名前（calc_votes など）は答えの文に書かない
- 「出席」には書面・代理人・電磁的方法による議決権の行使も含まれることなど、住民が誤解しやすい点は補う
- 定足数・出席・賛成の割合に触れる文章や質問で、マンションの基本情報があれば、calc_votes でこのマンションでの具体的な数（何戸・何人）も示す
- 専門家でない人に分かる言葉で書く。答えは総会提案の下書きを見直すための参考であり、法的助言ではない
- 文中の「人物A」（人名）「マンションA」（マンション名）「伏せた語A」（部屋番号など）は、名前を伏せた記号。そのまま使う

{KNOWLEDGE}"""


@dataclass
class Handler:
    """1回の相談で使う道具の実行役。"""

    profile: dict
    corpus: object | None = None            # core.corpus.Corpus（照らす規約）
    pasted: str = ""
    calls: list[str] = field(default_factory=list)
    read_law: set = field(default_factory=set)
    read_standard: set = field(default_factory=set)
    read_own: set = field(default_factory=set)
    calculated: bool = False
    answer: dict | None = None

    def run(self, name: str, args: dict) -> str:
        self.calls.append(name)
        fn = getattr(self, f"_{name}", None)
        if fn is None:
            return f"不明な道具です: {name}"
        try:
            return fn(**(args or {}))
        except TypeError as e:
            return f"道具の使い方が違います: {e}"

    def _list_topics(self) -> str:
        rows = [{"論点": t["id"], "内容": t["topic"], "区分": t["category"], "区分所有法": t.get("law", []),
                 "標準管理規約": t.get("standard", []), "確かめる点": t.get("check", ""), "注記": t.get("note", "")} for t in TOPICS]
        return json.dumps({"改正の論点": rows}, ensure_ascii=False) + "\n\n" + KNOWLEDGE

    def _get_law_articles(self, articles: list[str]) -> str:
        out = []
        for ref in articles[:MAX_ITEMS]:
            n = normalize_article_ref(ref)
            text = law().get(n)
            if text:
                self.read_law.add(n)
            out.append(text or f"【{ref}】区分所有法にこの条はありません。")
        return "\n\n".join(out)

    def _from(self, source, refs: list[str], name: str, seen: set) -> str:
        out = []
        for ref in refs[:MAX_ITEMS]:
            n = normalize_article_ref(ref)
            found = [a for a in source.articles if a.number == n]
            if not found:
                out.append(f"【{ref}】{name}にこの条はありません。")
            for a in found:
                seen.add(n)
                note = f"\n{a.note}" if a.note else ""
                out.append(f"【{a.label}" + (f"（{a.variant}案）" if a.variant else "") + "】" + note + "\n" + a.text())
        return "\n\n".join(out)

    def _get_standard_articles(self, articles: list[str]) -> str:
        return self._from(standard(), articles, "標準管理規約", self.read_standard)

    def _list_articles(self) -> str:
        if self.corpus is None:
            return "照らす規約は選ばれていません。お使いの規約の条は使えないので、標準管理規約と区分所有法で答える（必要なら、照らす規約を選ぶよう suggestion で勧める）。"
        k = self.corpus.main
        return json.dumps({"規約": [{"条": a.label, "見出し": a.caption} for a in k.articles],
                           "細則": {name: len(r.articles) for name, r in self.corpus.rules.items()}}, ensure_ascii=False)

    def _get_articles(self, articles: list[str], rule: str = "") -> str:
        if self.corpus is None:
            return self._list_articles()
        if rule:
            name = self.corpus.resolve(rule)
            if not name or name not in self.corpus.rules:
                return f"細則「{rule}」は見つかりません。list_articles の細則の名前を使ってください。"
            return f"【{name}】\n" + self._from(self.corpus.rules[name], articles, name, self.read_own)
        return self._from(self.corpus.main, articles, "お使いの規約", self.read_own)

    def _get_building_info(self) -> str:
        p = self.profile or {}
        info = {label: p.get(key) for key, label in PROFILE_FIELDS.items()}
        info["議決権の決め方"] = p.get("vote_rule", "分からない")
        if p.get("note"):
            info["メモ"] = p["note"]
        return json.dumps({"基本情報": info, "足りない項目": missing(p)}, ensure_ascii=False)

    def _calc_votes(self, kind: str, present_owners: int | None = None, present_votes: int | None = None) -> str:
        out = votes(self.profile, kind, present_owners, present_votes)
        if "need" not in out and "error" not in out:
            self.calculated = True
        return json.dumps(out, ensure_ascii=False)

    def _record_answer(self, summary: str, items: list[dict], need_info: list[str] | None = None,
                       followups: list[str] | None = None) -> str:
        problems = []
        for i, it in enumerate(items):
            for b in it.get("basis") or []:
                reason = self.check_basis(b)
                if reason:
                    problems.append({"番号": i, "根拠": f"{b.get('source')} {b.get('ref')}", "理由": reason})
            if it.get("verdict") in ("正しい", "言い方に注意", "誤り", "説明") and not (it.get("basis")):
                problems.append({"番号": i, "理由": "根拠がありません。根拠を付けるか、確かめられないなら「資料の外」にしてください"})
        if problems and self.calls.count("record_answer") < 3:
            return json.dumps({"受け付けませんでした": problems,
                               "直し方": "道具で読んだ条だけを根拠にする。読んでいない条は読んでから使う。確かめられない記述は「資料の外」にする"}, ensure_ascii=False)
        self.answer = finalize({"summary": summary, "items": items, "need_info": need_info or [], "followups": followups or []},
                               self, self.pasted)
        return json.dumps({"受け付けました": len(self.answer["items"])}, ensure_ascii=False)

    def check_basis(self, b: dict) -> str:
        """根拠が確かめられないときの理由（空なら OK）。"""
        src, ref = b.get("source", ""), str(b.get("ref", ""))
        n = normalize_article_ref(ref)
        if src == "区分所有法":
            if n not in law():
                return "区分所有法にこの条はありません"
            if n not in self.read_law:
                return "この条を get_law_articles で読んでいません"
        elif src == "標準管理規約":
            if not any(a.number == n for a in standard().articles):
                return "標準管理規約にこの条はありません"
            if n not in self.read_standard:
                return "この条を get_standard_articles で読んでいません"
        elif src == "お使いの規約":
            if self.corpus is None:
                return "照らす規約が選ばれていません"
            if n not in self.read_own:
                return "この条を get_articles で読んでいません"
        elif src == "計算":
            if not self.calculated:
                return "calc_votes で計算していません"
        elif src not in SOURCES:
            return "根拠の種類が違います"
        return ""


_INTERNAL = re.compile(r"\s*\(?（?(?:calc_votes|get_law_articles|get_standard_articles|get_articles|list_topics|get_building_info|record_answer)）?\)?\s*")


def _tidy_basis(b: dict) -> dict:
    """画面に出す根拠の形にそろえる（道具の名前を消し、資料名の重なり「改正法附則 附則第2条」を除く）。"""
    src, ref = b.get("source", ""), _INTERNAL.sub(" ", str(b.get("ref", ""))).strip()
    for head in (src, "附則" if src == "改正法附則" else "", "区分所有法" if src == "区分所有法" else ""):
        if head and ref.startswith(head) and ref != head:
            ref = ref[len(head):].strip()
    if src == "改正法附則" and not ref.startswith("附則"):
        ref = "附則" + ref
    return {"source": src, "ref": ref or ("この結果" if src == "計算" else "")}


def finalize(answer: dict, handler: Handler | None, pasted: str) -> dict:
    """根拠を確かめられない項目は「資料の外」に下げる（断定させない）。抜き出しが貼った文にない項目には印を付ける。"""
    items = []
    flat = re.sub(r"\s+", "", pasted or "")
    for it in answer.get("items") or []:
        it = {"quote": it.get("quote", "") or "", "verdict": it.get("verdict", "説明"), "comment": it.get("comment", ""),
              "basis": list(it.get("basis") or []), "suggestion": it.get("suggestion", "") or ""}
        if handler is not None:
            it["basis"] = [b for b in it["basis"] if not handler.check_basis(b)]
        it["basis"] = [_tidy_basis(b) for b in it["basis"]]
        for k in ("comment", "suggestion"):
            it[k] = _INTERNAL.sub("", it[k])
        if it["verdict"] in ("正しい", "言い方に注意", "誤り", "説明") and not it["basis"]:
            it["verdict"] = "資料の外"
            it["comment"] += "（根拠を確かめられなかったため、資料の外として扱います）"
        it["quote_found"] = (not it["quote"]) or re.sub(r"\s+", "", it["quote"]) in flat
        items.append(it)
    order = {v: i for i, v in enumerate(("誤り", "言い方に注意", "資料の外", "体裁", "正しい", "説明"))}
    # 大事な順（誤り → 言い方に注意 → 資料で確かめられない → 体裁 → 正しい）。同じ判定の中は、貼った文の順（想定ユーザーでの確認で分かった）
    items.sort(key=lambda x: (order.get(x["verdict"], 9),
                              flat.find(re.sub(r"\s+", "", x["quote"])) if x["quote"] and x["quote_found"] else 10**9))
    return {"summary": answer.get("summary", ""), "items": items,
            "need_info": [n for n in (answer.get("need_info") or []) if n in PROFILE_FIELDS.values()],
            "followups": list(answer.get("followups") or [])[:3]}


def counts(answer: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in (answer or {}).get("items") or []:
        out[it["verdict"]] = out.get(it["verdict"], 0) + 1
    return out


WEEKDAYS = "月火水木金土日"


def today_line(today=None) -> str:
    """今日の日付と、改正法が施行済みかどうか（「来年」「今年」を今日を基準に読ませる。想定ユーザーでの確認で分かった）。"""
    from datetime import date, datetime

    from core.review import JST

    d = today or datetime.now(JST).date()
    done = d >= date(2026, 4, 1)
    return (f"今日は {d.year}年{d.month}月{d.day}日（{WEEKDAYS[d.weekday()]}）。"
            + ("改正区分所有法はすでに施行されている（2026年4月1日）。これから招集する総会は、すべて改正後のルールによる。"
               "経過措置（2026年3月までに招集した総会は旧ルール）は、すでに過ぎた総会の扱いを聞かれたときだけ触れ、目立たせない"
               if done else "改正区分所有法の施行（2026年4月1日）より前。施行日をまたぐ総会の扱い（招集手続きを始めた日で決まる）に注意して答える"))


def user_message(mode: str, text: str, question: str, history: list[dict], has_rules: bool, today=None) -> str:
    """AI に送る依頼の文。history は前のやり取り（質問と、答えのまとめ）。"""
    parts = ["# 今日\n" + today_line(today) + "\n文章の中の「来年」「今年」「来月」や、年の書いていない日付・曜日は、今日を基準に読む。文章が書かれた年を勝手に決めつけない"]
    if mode == "check":
        parts.append("# 依頼\n次の文章を確かめてください（住民向けのニュース原稿・議事録・説明文など）。")
        if question:
            parts.append("# 特に見てほしいこと\n" + question)
        parts.append("# 貼った文\n" + text)
    else:
        parts.append("# 質問\n" + question)
        if text:
            parts.append("# 質問に添えた文\n" + text)
    if history:
        parts.append("# これまでのやり取り（同じ相談の続き）\n" + "\n".join(
            f"- 質問：{h.get('question') or '（文章の確認）'}\n  答えのまとめ：{h.get('summary', '')}" for h in history))
    parts.append("# 照らす規約\n" + ("選ばれている（list_articles・get_articles で読める）" if has_rules else "選ばれていない"))
    return "\n\n".join(parts)


def consult(mode: str, text: str, question: str, *, profile: dict, corpus=None, history: list[dict] | None = None,
            effort: str = "medium", on_step=None) -> tuple[dict, float, list[str]]:
    """相談を1回する。返すのは (答え, 費用の概算（ドル）, 使った道具)。"""
    handler = Handler(profile=profile or {}, corpus=corpus, pasted=text if mode == "check" else "")
    c = client()
    tools = [dict(t) for t in TOOL_DEFS] + [dict(RECORD_DEF)]
    tools[-1]["cache_control"] = {"type": "ephemeral"}
    messages = [{"role": "user", "content": user_message(mode, text, question, history or [], corpus is not None)}]
    usage_total: dict = {}
    for _turn in range(MAX_TURNS):
        with c.beta.messages.stream(
            model=MODEL, max_tokens=16000,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            tools=tools, messages=messages,
            output_config={"effort": effort},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        ) as stream:
            msg = stream.get_final_message()
        for k, v in (msg.usage.model_dump() if msg.usage else {}).items():
            if isinstance(v, (int, float)):
                usage_total[k] = usage_total.get(k, 0) + v
        if msg.stop_reason == "refusal":
            raise RuntimeError("AI が答えませんでした（refusal）")
        uses = [b for b in msg.content if getattr(b, "type", "") == "tool_use"]
        messages.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in msg.content]})
        if not uses:
            if handler.answer:
                break
            messages.append({"role": "user", "content": "record_answer で答えを記録してください。"})
            continue
        results = []
        for u in uses:
            if on_step:
                on_step(u.name)
            results.append({"type": "tool_result", "tool_use_id": u.id, "content": handler.run(u.name, u.input)})
        messages.append({"role": "user", "content": results})
        if handler.answer:
            break
    if handler.answer is None:
        raise RuntimeError("AI が答えを記録しませんでした")
    return handler.answer, cost_usd(usage_total), handler.calls


__all__ = ["KINDS", "PROFILE_FIELDS", "VOTE_RULES", "Handler", "clean_profile", "consult", "counts", "finalize",
           "mask_names", "missing", "unmask", "votes"]
