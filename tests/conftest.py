"""すべてのテストで、作業の保存先（private/work）を一時フォルダに差し替える。

テストが本物の作業のデータを書き換えないようにする。以前は一部のテストが差し替えずに
「起動時に止まった処理を片付ける」関数を呼び、動いている作業を「止まった」に書き換えていた
（想定ユーザーでの確認中に、説明の作成が「止まりました」と誤って出た原因）。
"""

import pytest

from app import store


@pytest.fixture(autouse=True)
def _isolated_work_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "WORK", tmp_path / "work")
    monkeypatch.setattr(store, "SEED", tmp_path / "no_seed")  # 想定ユーザーの作業はテストでは写さない
    (tmp_path / "work").mkdir()
    yield
