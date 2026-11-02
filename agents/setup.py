"""Managed Agents の Skill・環境・エージェントを登録（または更新）する。

エージェントは「1回作って、ID を使い回す」。実行のたびに作らない。
作成した ID は agents/state.json に保存する（ID は秘密情報ではない）。
設定を変えたら、このスクリプトを再実行すると新しい版として更新される。

使い方:  uv run python -m agents.setup
"""

from __future__ import annotations

import json
from pathlib import Path

from core.config import MODEL, ROOT, client
from core.tools import TOOL_DEFS
from core.topics import TOPICS

STATE = ROOT / "agents/state.json"
SKILL_DIR = ROOT / "skills/kiyaku-kaisei"
AGENT_NAME = "kiyaku-kaisei-reviewer"

SYSTEM = """あなたは、マンション管理組合の理事会・規約見直し担当者（専門家ではない）を手伝うアシスタントです。
現行の管理規約を、改正区分所有法（2026年4月施行）とマンション標準管理規約（2025年10月改正・単棟型）に照らして点検し、
改正対応が必要な箇所を、根拠条文付きで洗い出します。

- 作業の手順・論点表・指摘の書き方は、スキル「kiyaku-kaisei」に従ってください。最初にスキルの SKILL.md と reference/topics.md を読んでください。
- 規約・標準管理規約・区分所有法の本文は、必ずツールで取得してから使ってください。記憶に頼って条文を書かないでください。
- 指摘は record_findings で記録します。根拠を示せない指摘は出しません。
- 出力はすべて日本語です。成果は「総会提案の下書き」であり、法的助言ではありません。
"""


def topics_markdown() -> str:
    lines = [
        "# 改正論点の一覧（単棟型）",
        "",
        "出典：国交省「令和7年マンション標準管理規約改正の概要」（◎＝必須、○＝望ましい）、改正後の区分所有法。",
        "「標準」は標準管理規約（令和7年改正・単棟型）の条、「法」は区分所有法の条。",
        "",
        "| ID | 論点 | 区分 | 標準 | 法 | 確認すること |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for t in TOPICS:
        std = "、".join(f"第{n.replace('の', '条の') if 'の' in n else n + '条'}" for n in t["standard"])
        law = "、".join(f"第{n.replace('の', '条の') if 'の' in n else n + '条'}" for n in t["law"]) or "—"
        lines.append(f"| {t['id']} | {t['topic']} | {t['category']} | {std} | {law} | {t['check']} |")
    return "\n".join(lines) + "\n"


def skill_files() -> list[tuple[str, bytes, str]]:
    return [
        ("kiyaku-kaisei/SKILL.md", (SKILL_DIR / "SKILL.md").read_bytes(), "text/markdown"),
        ("kiyaku-kaisei/reference/topics.md", topics_markdown().encode("utf-8"), "text/markdown"),
    ]


def load_state() -> dict:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def main() -> None:
    c = client()
    state = load_state()

    # 1. Skill（改正知識）
    if state.get("skill_id"):
        version = c.skills.versions.create(skill_id=state["skill_id"], files=skill_files())
        print(f"Skill を更新: {state['skill_id']}（版 {version.id}）")
    else:
        skill = c.skills.create(files=skill_files(), display_name="管理規約 改正対応チェック")
        state["skill_id"] = skill.id
        print(f"Skill を作成: {skill.id}")

    # 2. 環境（外部ネットワークなし。ツールはアプリ側で実行する）
    if not state.get("environment_id"):
        env = c.beta.environments.create(
            name="kiyaku-kaisei",
            config={"type": "cloud", "networking": {"type": "limited", "allow_package_managers": False, "allow_mcp_servers": False}},
        )
        state["environment_id"] = env.id
        print(f"環境を作成: {env.id}")

    # 3. エージェント
    params = dict(
        name=AGENT_NAME,
        model=MODEL,
        system=SYSTEM,
        description="管理規約を改正区分所有法・標準管理規約に照らして点検し、根拠付きで指摘する",
        skills=[{"type": "custom", "skill_id": state["skill_id"], "version": "latest"}],
        tools=[
            {
                "type": "agent_toolset_20260401",
                "default_config": {"enabled": False},
                "configs": [
                    # スキルのファイルを読むためだけに使う
                    {"name": "read", "enabled": True, "permission_policy": {"type": "always_allow"}},
                    {"name": "glob", "enabled": True, "permission_policy": {"type": "always_allow"}},
                    {"name": "grep", "enabled": True, "permission_policy": {"type": "always_allow"}},
                ],
            },
            *TOOL_DEFS,
        ],
    )
    if state.get("agent_id"):
        current = c.beta.agents.retrieve(state["agent_id"])
        agent = c.beta.agents.update(state["agent_id"], version=current.version, **params)
        print(f"エージェントを更新: {agent.id}（版 {agent.version}）")
    else:
        agent = c.beta.agents.create(**params)
        print(f"エージェントを作成: {agent.id}（版 {agent.version}）")
    state["agent_id"] = agent.id
    state["agent_version"] = agent.version

    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"保存: {STATE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
