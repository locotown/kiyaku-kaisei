"""審査員向けの公開版のログイン（11/8 作者の判断）。

手元で使うとき（環境変数 KIYAKU_ACCOUNTS がないとき）は何もしない。公開先では次を守る：
  - ID とパスワードでログインする。パスワードはハッシュ（PBKDF2-SHA256）で持つ
  - アカウントごとの期限（日本時間のその日の終わり）を過ぎるとログインできない。操作のない時間が12時間続くとログインし直し
  - 作業と相談に持ち主を記録し、自分のものだけを開ける（管理者は全部）
  - AI の費用は、アカウントごとの上限と全体の上限を超えたら新しい AI の処理を始めない
  - ログインの失敗が続く相手は、しばらく受け付けない
アカウントの一覧は公開先の環境変数にだけ置く（リポジトリに入れない）。作り方は scripts/make_accounts.py。
"""

from __future__ import annotations

import base64
import contextvars
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta

from core.review import JST

COOKIE = "kiyaku_session"
IDLE = 12 * 3600                       # 操作のない時間がこれを超えたら、ログインし直す
FAIL_WINDOW, FAIL_MAX = 15 * 60, 8     # この時間に、この回数失敗したら、しばらく受け付けない
ITER = 200_000

CURRENT: contextvars.ContextVar[dict | None] = contextvars.ContextVar("kiyaku_user", default=None)
_fails: dict[str, list[float]] = {}
_secret_fallback = secrets.token_bytes(32)


def accounts() -> dict[str, dict]:
    raw = os.environ.get("KIYAKU_ACCOUNTS", "").strip()
    if not raw:
        return {}
    try:
        items = json.loads(raw)
    except ValueError:
        return {}
    return {a["id"]: a for a in items if isinstance(a, dict) and a.get("id") and a.get("pw")}


def enabled() -> bool:
    """ログインを使うか。KIYAKU_ACCOUNTS が入っていれば、読み取れなくても使う（壊れた値で誰でも入れる状態にしない）。"""
    return bool(os.environ.get("KIYAKU_ACCOUNTS", "").strip())


def hash_password(pw: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt.encode("ascii"), ITER).hex()
    return f"pbkdf2${ITER}${salt}${h}"


def _check_password(pw: str, stored: str) -> bool:
    try:
        _, it, salt, h = stored.split("$")
        got = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt.encode("ascii"), int(it)).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(got, h)


def expires_at(acc: dict) -> float:
    """アカウントが使えなくなる時刻（期限の日の、日本時間の終わり）。期限がなければ無期限。"""
    until = acc.get("until")
    if not until:
        return float("inf")
    try:
        d = datetime.strptime(until, "%Y-%m-%d").replace(tzinfo=JST) + timedelta(days=1)
    except ValueError:
        return 0.0
    return d.timestamp()


def until_label(acc: dict) -> str:
    u = acc.get("until") or ""
    try:
        d = datetime.strptime(u, "%Y-%m-%d")
        return f"{d.month}月{d.day}日まで"
    except ValueError:
        return ""


def blocked(key: str) -> bool:
    now = time.time()
    _fails[key] = [t for t in _fails.get(key, []) if now - t < FAIL_WINDOW]
    return len(_fails[key]) >= FAIL_MAX


def login(user_id: str, pw: str, client: str) -> tuple[dict | None, str]:
    """(アカウント, 断った理由)。理由は画面に出す日本語。
    失敗の数は、接続元ごとと、接続元×ID ごとに数える（ID だけで数えると、他人が審査員のログインを止められる）。"""
    keys = (f"ip:{client}", f"ipid:{client}|{user_id}")
    for key in keys:
        if blocked(key):
            return None, "ログインの失敗が続いたため、しばらく受け付けません。15分ほどしてからお試しください。"
    acc = accounts().get(user_id)
    if not acc or not _check_password(pw, acc["pw"]):
        if len(_fails) > 10_000:   # 記録が増えすぎないように、古いものを捨てる
            for k in [k for k in _fails if not blocked(k)]:
                _fails.pop(k, None)
        for key in keys:
            _fails.setdefault(key, []).append(time.time())
        return None, "ID かパスワードが違います。"
    if time.time() >= expires_at(acc):
        return None, "このアカウントの期限が過ぎました。"
    return acc, ""


def _secret() -> bytes:
    s = os.environ.get("KIYAKU_SESSION_SECRET", "")
    return s.encode("utf-8") if s else _secret_fallback   # 決めていなければ、起動のたびに変わる（ログインし直しになる）


def _sign(body: bytes) -> str:
    return base64.urlsafe_b64encode(hmac.new(_secret(), body, hashlib.sha256).digest()).decode().rstrip("=")


def make_cookie(user_id: str) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"u": user_id, "t": int(time.time())}).encode()).decode().rstrip("=")
    return body + "." + _sign(body.encode())


def from_cookie(value: str | None) -> dict | None:
    """クッキーからアカウントを取り出す。署名が違う・期限切れ・操作のない時間が長すぎるときは None。"""
    if not value or "." not in value:
        return None
    body, sig = value.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(body.encode())):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except ValueError:
        return None
    acc = accounts().get(data.get("u", ""))
    now = time.time()
    if not acc or now >= expires_at(acc) or now - float(data.get("t", 0)) > IDLE:
        return None
    return acc


def user_id() -> str:
    acc = CURRENT.get()
    return acc["id"] if acc else ""


def is_admin() -> bool:
    acc = CURRENT.get()
    return bool(acc and acc.get("admin"))


def can_open(owner: str | None) -> bool:
    """今のアカウントが、この持ち主のものを開けるか。ログインを使わないときは、いつでも開ける。"""
    if not enabled():
        return True
    if is_admin():
        return True
    return bool(owner) and owner == user_id()


# ---- AI の費用の上限 ----------------------------------------------------------------

def limits() -> tuple[float, float]:
    """（アカウントごとの上限, 全体の上限）。ドル。環境変数で変えられる。"""
    def num(name: str, default: float) -> float:
        try:
            return float(os.environ.get(name, default))
        except ValueError:
            return default
    return num("KIYAKU_LIMIT_USER_USD", 20.0), num("KIYAKU_LIMIT_TOTAL_USD", 200.0)


def _usd(entry) -> float:
    try:
        c = entry.get("cost") or {}
        if isinstance(c, dict):
            return float(c.get("amount") or 0) / 100
        return float(c or 0)
    except (TypeError, ValueError, AttributeError):
        return 0.0


def spent() -> tuple[float, float]:
    """（今のアカウントが使った額, 全体で使った額）。作業の費用の記録と、相談の費用から数える。"""
    from app import store

    me = user_id()
    mine = total = 0.0
    if store.WORK.exists():
        for f in store.WORK.glob("*/work.json"):
            try:
                w = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            costs = w.get("costs") or []
            notes = [b for b in w.get("notes") or [] if isinstance(b, dict)]
            if w.get("seeded"):
                # 写したサンプル（想定ユーザーの作業）に元からある費用は数えない。写したあとに動かした AI の費用は数える
                n_costs, old_notes = _seed_base(f.parent.name, w)
                costs = costs[n_costs:]
                notes = [b for b in notes if b.get("id") not in old_notes]
            usd = sum(_usd(e) for e in costs)
            usd += sum(float(b.get("cost_usd") or 0) for b in notes)   # 写真の読み取り
            total += usd
            if w.get("owner") == me:
                mine += usd
    if store.CONSULT.exists():
        for f in store.CONSULT.glob("*.json"):
            if f.name.startswith("profile"):
                continue
            try:
                c = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            usd = float(c.get("cost_total") or 0)
            total += usd
            if c.get("owner") == me:
                mine += usd
    return mine, total


def _seed_base(work_id: str, w: dict) -> tuple[int, set]:
    """写したサンプルに、写したときから入っていた（費用の記録の数, 写真の読み取りの id）。"""
    if isinstance(w.get("seed_costs"), int):
        return w["seed_costs"], set(w.get("seed_notes") or [])
    from app import store   # 記録する前に写した作業は、元のサンプルから数える
    seed = store.SEED / work_id.rsplit("-", 1)[0] / "work.json"
    try:
        d = json.loads(seed.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = w
    return len(d.get("costs") or []), {b.get("id") for b in d.get("notes") or [] if isinstance(b, dict)}


BUSY_WORK = ("点検中", "改定案作成中", "検討資料作成中", "説明文作成中")
MAX_RUNNING = 2   # 同時に動かせる AI の処理の数（費用は終わってから記録されるため、並べて上限をすり抜けないように）


def running() -> int:
    """今のアカウントで、動いている AI の処理の数。"""
    from app import store

    me, n = user_id(), 0
    for f in list(store.WORK.glob("*/work.json")) if store.WORK.exists() else []:
        try:
            w = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if w.get("owner") != me:
            continue
        n += w.get("status") in BUSY_WORK
        n += sum(1 for b in w.get("notes") or [] if isinstance(b, dict) and b.get("status") == "読み取り中")
    for f in list(store.CONSULT.glob("*.json")) if store.CONSULT.exists() else []:
        if f.name.startswith("profile"):
            continue
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if c.get("owner") == me and any(t.get("status") == "考え中" for t in c.get("turns") or []):
            n += 1
    return n


def ai_refusal() -> str:
    """新しい AI の処理を始めてよければ空。だめなら画面に出す理由。"""
    if not enabled() or is_admin():
        return ""
    mine, total = spent()
    per_user, all_users = limits()
    if total >= all_users:
        return "この公開版の AI の費用が上限に達したため、新しい AI の処理は始められません。これまでの作業は見られます。"
    if mine >= per_user:
        return f"このアカウントの AI の費用が上限（約${per_user:.0f}）に達したため、新しい AI の処理は始められません。これまでの作業は見られます。"
    if running() >= MAX_RUNNING:
        return f"AI の処理が{MAX_RUNNING}つ動いています。終わってから、もう一度お試しください。"
    return ""
