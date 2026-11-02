"""改定案の参照・枝番の検査と、採点役に参照先の条を渡す処理のテスト。API は呼ばない。"""

from core.config import ROOT
from core.corpus import Corpus
from core.draft import Amendment, numbering_warnings, references
from core.ingest import load_collection

CORPUS = Corpus.from_collection(load_collection(ROOT / "evals/data/old_collection.txt"))


def amend(kind, article, text, document="規約"):
    return Amendment(kind, article, None if kind == "新設" else article, "", text, "", [], [], ["第1条"], document=document)


def test_references_skip_other_laws_and_self():
    a = amend("改正", "第49条", "第49条　前条第1項に定める…第45条第2項による。区分所有法第31条第1項及び標準管理規約第47条並びに建物の区分所有等に関する法律第62条")
    r = amend("改正", "第3条", "第3条　規約第45条第7項による。", document="○○マンション総会運営細則")
    assert references([a, r], CORPUS) == {("規約", "45")}


def test_numbering_warnings():
    gap = amend("新設", "第69条の3", "第69条の3　第62条第4項を準用する。")
    w = numbering_warnings([gap], CORPUS)
    assert any("欠番" in x for x in w)
    ok = [amend("新設", "第69条の2", "第69条の2　…"), amend("新設", "第69条の3", "第69条の3　第62条を準用する。")]
    assert not numbering_warnings(ok, CORPUS)
    dangling = amend("改正", "第49条", "第49条　第99条による。")
    assert any("第99条" in x and "改定後にありません" in x for x in numbering_warnings([dangling], CORPUS))
    deleted = [amend("削除", "第62条", "第62条　削除"), amend("新設", "第69条の2", "第69条の2　第62条を準用する。")]
    assert any("第62条" in x for x in numbering_warnings(deleted, CORPUS))


def test_share_references_uploads_only_referenced_articles():
    from core.drafting import REF_MOUNT, DraftToolHandler
    from core.findings import Finding

    class Fake:
        def __init__(self):
            self.uploaded, self.added, self.deleted = [], [], []
            self.beta = self
            self.files = self
            self.sessions = self
            self.resources = self

        def upload(self, file, betas):
            self.uploaded.append(file[1].decode())
            return type("F", (), {"id": f"file_{len(self.uploaded)}"})()

        def add(self, session_id, file_id, type, mount_path, betas):
            self.added.append((file_id, mount_path))
            return type("R", (), {"id": f"res_{len(self.added)}"})() if False else _R(f"res_{len(self.added)}")

        def delete(self, resource_id, session_id, betas):
            self.deleted.append(resource_id)

    class _R:
        def __init__(self, id):
            self.id = id

    finding = Finding("第49条", "1-1", "必須", "", "", [], [], "規約", "")
    h = DraftToolHandler(CORPUS.main, [finding], CORPUS.rules)
    fake, logs = Fake(), []
    h.attach(fake, "sesn_x", lambda k, t: logs.append(t))
    amendments = [amend("改正", "第49条", "第49条　第45条第2項及び第49条による。"), amend("新設", "第69条の2", "第69条の2　第62条を準用する。")]
    assert h.share_references(amendments) == 2
    text = fake.uploaded[0]
    assert "■ 規約 第45条" in text and "■ 規約 第62条" in text and "■ 規約 第49条" not in text  # 対象の条は確認基準で渡し済み
    assert fake.added == [("file_1", REF_MOUNT)]
    assert h.share_references(amendments) == 0  # 変わらなければ置き直さない
    amendments.append(amend("改正", "第50条", "第50条　第28条による。"))
    assert h.share_references(amendments) == 3 and fake.deleted == ["res_1"] and fake.added[-1] == ("file_2", REF_MOUNT)
