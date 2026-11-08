"""点検の作業データ（アップロードした規約、指摘、採用・不採用の判断、改定案）を保存する。

保存先は private/work/<作業ID>/。private/ は .gitignore 済みで、コミットされない。
判断の記録の正本はここ（docs/ARCHITECTURE.md）。
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from datetime import datetime
from pathlib import Path

from core import auth
from core.config import DATA, ROOT
from core.review import JST

WORK = DATA / "work"
# 想定ユーザー（架空）が使った作業の記録。リポジトリに入れて配り、一覧を開いたときに private/work へ写す
# （写しなので、開いて操作してもリポジトリのファイルは変わらない）。中身はアプリのサンプル（架空）だけ
SEED = ROOT / "data/public/persona_works"
# AI 相談（ととのう規約に相談する）の記録と、マンションの基本情報。貼った文には人名などが入りうるので、private/ にだけ置く
CONSULT = DATA / "consult"
_lock = threading.Lock()


def seed_persona_works() -> int:
    """想定ユーザーの作業のうち、まだ private/work にないものを写す。写した件数を返す。

    公開版（ログインあり）では、アカウントごとに別の写しを作り、持ち主をそのアカウントにする
    （ログインしてすぐ、AI を待たずに総会まで済んだ作業を触れるように。ほかの人の写しは見えない）。"""
    import shutil

    if not SEED.exists():
        return 0
    me = auth.user_id() if auth.enabled() else ""
    if auth.enabled() and not me:
        return 0
    n = 0
    for d in SEED.iterdir():
        dest = WORK / (f"{d.name}-{me}" if me else d.name)
        if (d / "work.json").exists() and not dest.exists():
            WORK.mkdir(parents=True, exist_ok=True)
            shutil.copytree(d, dest)
            if me:
                data = json.loads((dest / "work.json").read_text(encoding="utf-8"))
                data["owner"] = me
                data["seeded"] = True   # 写したサンプル。中の費用の記録は、公開版の費用の上限に数えない
                (dest / "work.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            n += 1
    return n


class WorkNotFound(LookupError):
    """作業がない（または作業IDの形が正しくない）。"""


def new_id() -> str:
    return datetime.now(JST).strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)


def path(work_id: str) -> Path:
    if len(work_id) > 64 or not work_id.replace("-", "").isalnum() or not work_id.isascii():   # 長すぎる ID で 500 になった
        raise WorkNotFound(work_id)
    return WORK / work_id


def load(work_id: str) -> dict:
    p = path(work_id) / "work.json"
    if not p.exists():
        raise WorkNotFound(work_id)
    return json.loads(p.read_text(encoding="utf-8"))


def save(work_id: str, data: dict) -> None:
    d = path(work_id)
    d.mkdir(parents=True, exist_ok=True)
    data.setdefault("status_since", time.time())
    with _lock:
        tmp = d / "work.json.tmp"
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(d / "work.json")


def update(work_id: str, **changes) -> dict:
    with _lock:
        data = json.loads((path(work_id) / "work.json").read_text(encoding="utf-8"))
        if "status" in changes and changes["status"] != data.get("status"):
            data["status_since"] = time.time()  # 処理の経過時間を示すため
        data.update(changes)
        tmp = path(work_id) / "work.json.tmp"
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path(work_id) / "work.json")
    return data


def mutate(work_id: str, fn) -> dict:
    """作業の記録を読み、fn で書き換えて保存する（読み・書きの間に、ほかの処理が割り込まないようにする）。"""
    with _lock:
        p = path(work_id) / "work.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        fn(data)
        tmp = path(work_id) / "work.json.tmp"
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
    return data


def append_log(work_id: str, kind: str, text: str) -> None:
    with _lock:
        p = path(work_id) / "work.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data.setdefault("log", []).append({"t": datetime.now(JST).strftime("%H:%M:%S"), "ts": time.time(), "kind": kind, "text": text})
        tmp = path(work_id) / "work.json.tmp"
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)


BUSY_OR_ERROR = ("点検中", "改定案作成中", "検討資料作成中", "説明文作成中", "エラー", "改定案エラー", "検討資料エラー", "説明文エラー")


def display_status(data: dict) -> str:
    """画面と一覧に出す状態。保存した値ではなく中身（総会の結果・説明・検討資料）から決める
    （作り直しのあとで「改定案あり」に戻ったように見えた、という声から）。処理中・エラーはそのまま。"""
    status = data.get("status", "")
    if status in BUSY_OR_ERROR or not data.get("draft"):
        return status
    if any(((data.get("meeting") or {}).get("results") or {}).values()):
        return "総会の結果あり"
    if data.get("explain"):
        return "説明文あり"
    if data.get("board"):
        return "検討資料あり"
    return status


def list_works(all_users: bool = False) -> list[dict]:
    """作業の一覧。公開版では今のアカウントのものだけ（all_users=True はサーバーの起動時の点検用）。"""
    seed_persona_works()
    if not WORK.exists():
        return []
    out = []
    for d in sorted(WORK.iterdir(), reverse=True):
        f = d / "work.json"
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            if not all_users and not auth.can_open(data.get("owner")):   # 公開版：ほかの人の作業は一覧に出さない
                continue
            status = display_status(data)  # 作業の画面の表示とそろえる
            out.append({"id": d.name, "name": data.get("name", ""), "status": status,
                        "findings": len(data.get("findings", [])), "persona": data.get("persona")})
    return out


# ---- AI 相談 ----------------------------------------------------------------------

def consult_path(cid: str) -> Path:
    if not cid.replace("-", "").isalnum():
        raise WorkNotFound(cid)
    return CONSULT / f"{cid}.json"


def load_consult(cid: str) -> dict:
    p = consult_path(cid)
    if not p.exists():
        raise WorkNotFound(cid)
    return json.loads(p.read_text(encoding="utf-8"))


def save_consult(data: dict) -> None:
    with _lock:
        CONSULT.mkdir(parents=True, exist_ok=True)
        p = consult_path(data["id"])
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(p)


def update_consult(cid: str, fn) -> dict:
    """読み直してから fn(data) で書き換えて保存する（別のスレッドの書き込みを消さないように）。"""
    with _lock:
        p = consult_path(cid)
        data = json.loads(p.read_text(encoding="utf-8"))
        fn(data)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(p)
        return data


def delete_consult(cid: str) -> None:
    p = consult_path(cid)
    if p.exists():
        p.unlink()


def list_consults() -> list[dict]:
    if not CONSULT.exists():
        return []
    out = []
    for f in sorted(CONSULT.glob("*.json"), reverse=True):
        if f.name.startswith("profile"):
            continue
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if auth.can_open(c.get("owner")):   # 公開版：ほかの人の相談は出さない
            out.append(c)
    return out


def _profile_path() -> Path:
    """マンションの基本情報。公開版ではアカウントごと（ほかの人が入れた戸数で計算しないように）。"""
    me = auth.user_id() if auth.enabled() else ""
    return CONSULT / (f"profile-{me}.json" if me else "profile.json")


def load_profile() -> dict:
    p = _profile_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save_profile(profile: dict) -> None:
    with _lock:
        CONSULT.mkdir(parents=True, exist_ok=True)
        _profile_path().write_text(json.dumps(profile, ensure_ascii=False, indent=1), encoding="utf-8")
