# user_store.py
import os, json, time
from typing import Dict, Any

DEFAULT_PATH = os.getenv("USERS_PATH", "./data/users.json")

def _ensure_path(path: str) -> None:
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False)

def load_users(path: str = DEFAULT_PATH) -> Dict[str, Any]:
    _ensure_path(path)
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f) or {}
        except json.JSONDecodeError:
            return {}

def save_users(users: Dict[str, Any], path: str = DEFAULT_PATH) -> None:
    _ensure_path(path)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)

def upsert_user(tg_user, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    """تسجيل/تحديث المستخدم تلقائياً."""
    users = load_users(path)
    uid = str(tg_user.id)
    now = int(time.time())
    entry = users.get(uid, {})
    entry.update({
        "id": tg_user.id,
        "is_bot": getattr(tg_user, "is_bot", False),
        "username": getattr(tg_user, "username", None),
        "first_name": getattr(tg_user, "first_name", None),
        "last_name": getattr(tg_user, "last_name", None),
        "language_code": getattr(tg_user, "language_code", None),
        "last_seen_ts": now
    })
    users[uid] = entry
    save_users(users, path)
    return entry
