# user_index.py
import os, json
from typing import Optional, Dict, Any

DEFAULT_PATH = os.getenv("USER_INDEX_PATH", "./data/user_index.json")

def _ensure() -> Dict[str, Any]:
    folder = os.path.dirname(DEFAULT_PATH)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    if not os.path.exists(DEFAULT_PATH):
        with open(DEFAULT_PATH, "w", encoding="utf-8") as f:
            json.dump({"by_username": {}, "by_phone": {}, "by_id": {}}, f)
    with open(DEFAULT_PATH, "r", encoding="utf-8") as f:
        try: d = json.load(f)
        except json.JSONDecodeError: d = {}
    d.setdefault("by_username", {})
    d.setdefault("by_phone", {})
    d.setdefault("by_id", {})
    return d

def _save(d: Dict[str, Any]) -> None:
    tmp = DEFAULT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DEFAULT_PATH)

def upsert(user_id: int, username: Optional[str] = None, phone: Optional[str] = None) -> None:
    d = _ensure()
    d["by_id"][str(user_id)] = {"username": username or "", "phone": phone or ""}
    if username:
        d["by_username"][username.lower()] = int(user_id)
    if phone:
        d["by_phone"][phone] = int(user_id)
    _save(d)

def find_by_username(username: str) -> Optional[int]:
    d = _ensure()
    return d["by_username"].get(username.lower())

def find_by_phone(phone: str) -> Optional[int]:
    d = _ensure()
    return d["by_phone"].get(phone)

def get_cached(user_id: int) -> Dict[str, str]:
    d = _ensure()
    return d["by_id"].get(str(user_id), {"username": "", "phone": ""})
