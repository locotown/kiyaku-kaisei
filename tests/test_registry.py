"""使う API キーに合わせたエージェントの登録（agents/registry.py）。本物の API は呼ばない。"""

import json

import pytest

from agents import registry as R
from agents import setup as S


class Missing(Exception):
    pass


class FakeClient:
    """開発者のワークスペースの ID だけが見える、偽の Managed Agents。"""

    def __init__(self, visible: set[str]):
        self.visible = visible
        self.created: list[str] = []
        outer = self

        class Agents:
            @staticmethod
            def retrieve(agent_id):
                if agent_id not in outer.visible:
                    raise Missing(agent_id)
                return type("A", (), {"id": agent_id, "version": 1})()

            @staticmethod
            def create(**params):
                new = f"agent_new_{len(outer.created) + 1}"
                outer.created.append(params["name"])
                outer.visible.add(new)
                return type("A", (), {"id": new, "version": 1})()

            @staticmethod
            def update(agent_id, version, **params):
                outer.created.append("update:" + params["name"])
                return type("A", (), {"id": agent_id, "version": version + 1})()

        class Envs:
            @staticmethod
            def create(**kw):
                outer.created.append("env")
                return type("E", (), {"id": "env_new"})()

        class Skills:
            @staticmethod
            def create(**kw):
                outer.created.append("skill")
                return type("S", (), {"id": "skill_new"})()

            class versions:
                @staticmethod
                def create(**kw):
                    outer.created.append("skill_version")
                    return type("V", (), {"id": "v2"})()

        self.beta = type("B", (), {"agents": Agents, "environments": Envs})()
        self.skills = Skills


@pytest.fixture
def setup_env(monkeypatch, tmp_path):
    committed = tmp_path / "state.json"
    committed.write_text(json.dumps({"skill_id": "skill_dev", "environment_id": "env_dev", "agent_id": "agent_dev",
                                     "agent_version": 3, "drafter_id": "drafter_dev", "drafter_version": 2}))
    monkeypatch.setattr(R, "COMMITTED", committed)
    monkeypatch.setattr(R, "PRIVATE", tmp_path / "private_agents")
    monkeypatch.setattr(R, "NOT_MINE", (Missing,))
    return committed


def use(monkeypatch, key, fake):
    monkeypatch.setattr(R, "api_key", lambda: key)
    monkeypatch.setattr(R, "client", lambda: fake)


def test_developer_key_uses_committed_agents_without_registering(setup_env, monkeypatch):
    fake = FakeClient({"agent_dev", "drafter_dev"})
    use(monkeypatch, "sk-dev", fake)
    state = R.agent_state()
    assert state["agent_id"] == "agent_dev" and fake.created == []          # 開発者はすぐに使える（登録しない）
    # 開発者が agents/state.json を更新したら、次からその版を使う（手元に古い写しを持たない）
    setup_env.write_text(json.dumps({**json.loads(setup_env.read_text()), "agent_version": 4}))
    assert R.agent_state()["agent_version"] == 4


def test_other_key_registers_once_and_keeps_ids_private(setup_env, monkeypatch):
    fake = FakeClient(set())                                               # 開発者の登録は見えない
    use(monkeypatch, "sk-another-condo", fake)
    said = []
    state = R.agent_state(lambda kind, text: said.append((kind, text)))
    assert state["agent_id"].startswith("agent_new") and state["drafter_id"].startswith("agent_new")
    assert state["environment_id"] == "env_new" and state["skill_id"] == "skill_new"
    assert any("はじめて使う API キー" in t for _, t in said)
    files = list((R.PRIVATE).glob("state-*.json"))
    assert len(files) == 1 and "sk-another-condo" not in files[0].read_text()  # キーそのものは保存しない
    assert json.loads(setup_env.read_text())["agent_id"] == "agent_dev"      # 開発者の登録には触らない
    n = len(fake.created)
    assert R.agent_state()["agent_id"] == state["agent_id"] and len(fake.created) == n  # 2回目は登録しない


def test_registered_agents_follow_app_updates(setup_env, monkeypatch):
    fake = FakeClient(set())
    use(monkeypatch, "sk-another-condo", fake)
    first = R.agent_state()
    monkeypatch.setattr(S, "SYSTEM", S.SYSTEM + "\n- 追加の注意")               # アプリの更新で指示文が変わった
    said = []
    second = R.agent_state(lambda kind, text: said.append(text))
    assert second["agent_id"] == first["agent_id"] and second["agent_version"] == first["agent_version"] + 1
    assert any("アプリが更新された" in t for t in said)
