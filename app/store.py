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

from core.config import ROOT
from core.review import JST

WORK = ROOT / "private/work"
_lock = threading.Lock()


class WorkNotFound(LookupError):
    """作業がない（または作業IDの形が正しくない）。"""


def new_id() -> str:
    return datetime.now(JST).strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3)


def path(work_id: str) -> Path:
    if not work_id.replace("-", "").isalnum():
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


def list_works() -> list[dict]:
    if not WORK.exists():
        return []
    out = []
    for d in sorted(WORK.iterdir(), reverse=True):
        f = d / "work.json"
        if f.exists():
            data = json.loads(f.read_text(encoding="utf-8"))
            out.append({"id": d.name, "name": data.get("name", ""), "status": data.get("status", ""),
                        "findings": len(data.get("findings", []))})
    return out
