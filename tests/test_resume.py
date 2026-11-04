"""改定案づくりの「つなぎ直し」と「途中から再開」（core/drafting.py の _catch_up・_drive）。

API の代わりに偽の相手を使い、答えていない道具の呼び出しにだけ答えること、
通信が切れても同じ呼び出しに二度答えないことを確かめる。費用はかからない。
"""

from types import SimpleNamespace as NS

import httpx2

from core import drafting as D


def ev(eid, etype, **kw):
    return NS(id=eid, type=etype, **kw)


def idle(eid, reason):
    return ev(eid, "session.status_idle", stop_reason=NS(type=reason))


def tool_use(eid):
    return ev(eid, "agent.custom_tool_use", name="get_articles", input={"articles": ["47"]})


class FakeStream:
    def __init__(self, events, fail_after=None):
        self.events, self.fail_after = events, fail_after

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def __iter__(self):
        for k, e in enumerate(self.events):
            if self.fail_after is not None and k == self.fail_after:
                raise httpx2.ReadError("切断")
            yield e


class FakeClient:
    """sessions.events の list・stream・send だけを持つ偽の相手。"""

    def __init__(self, history, streams):
        self.history, self.streams, self.sent = history, list(streams), []
        events = NS(list=self._list, stream=self._stream, send=self._send)
        self.beta = NS(sessions=NS(events=events))

    def _list(self, session_id, order="asc"):
        return list(self.history)

    def _stream(self, session_id):
        return self.streams.pop(0)

    def _send(self, session_id, events):
        self.sent.extend(events)


class FakeHandler:
    def __init__(self):
        self.calls = 0

    def run(self, name, args):
        self.calls += 1
        return "第47条の文"


def answers(c):
    return [e["custom_tool_use_id"] for e in c.sent if e["type"] == "user.custom_tool_result"]


def test_catch_up_answers_only_unanswered():
    history = [
        tool_use("t1"), ev("r1", "user.custom_tool_result", custom_tool_use_id="t1"),  # 答えてある
        ev("g1", "span.outcome_evaluation_end", iteration=0, result="needs_revision", explanation="直す"),
        tool_use("t2"),                                                                 # 止まっている間に来た：答えていない
        idle("i1", "requires_action"),
    ]
    c, h, evals = FakeClient(history, []), FakeHandler(), []
    done = D._catch_up(c, "sesn_x", h, lambda k, t: None, evals, set(), quiet=True)
    assert done == ""                         # 答えたので、AI はまた動き出す
    assert answers(c) == ["t2"] and h.calls == 1
    assert evals[0]["result"] == "needs_revision"  # 採点の結果は集め直す


def test_catch_up_already_finished_costs_nothing():
    history = [tool_use("t1"), ev("r1", "user.custom_tool_result", custom_tool_use_id="t1"), idle("i1", "end_turn")]
    c, h = FakeClient(history, []), FakeHandler()
    assert D._catch_up(c, "sesn_x", h, lambda k, t: None, [], set(), quiet=True) == "end_turn"
    assert c.sent == [] and h.calls == 0      # 何も送らない（追加の費用なし）


def test_drive_reconnects_without_double_answers(monkeypatch):
    monkeypatch.setattr(D.time, "sleep", lambda s: None)
    # 1回目のストリーム：t1 に答えたあと、t2 を受け取る前に切れる
    first = FakeStream([tool_use("t1"), tool_use("t2")], fail_after=1)
    # つなぎ直したとき：過去には t1（答えた）と t2（答えていない）。ライブのストリームは t2 を再送し、終わる
    history = [tool_use("t1"), ev("r1", "user.custom_tool_result", custom_tool_use_id="t1"), tool_use("t2")]
    second = FakeStream([tool_use("t2"), idle("i9", "end_turn")])
    c, h, logs = FakeClient(history, [first, second]), FakeHandler(), []
    stop = D._drive(c, "sesn_x", h, lambda k, t: logs.append(k), [], started=D.time.monotonic(), deadline=600,
                    plan={"deadline_min": 10}, kickoff={"type": "user.define_outcome"})
    assert stop == "end_turn"
    assert answers(c) == ["t1", "t2"]         # どちらにも1回ずつ
    assert h.calls == 2
    assert "error" in logs                    # つなぎ直したことは作業の記録に残す
