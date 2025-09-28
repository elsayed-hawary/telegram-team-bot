# team_store.py
import os, json
from typing import Dict, Any, Optional

DEFAULT_PATH = os.getenv("TEAMS_PATH", "./data/teams.json")

def _ensure_path(path: str) -> None:
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"teams": {}, "memberships": {}}, f, ensure_ascii=False)

def _load(path: str = DEFAULT_PATH) -> Dict[str, Any]:
    _ensure_path(path)
    with open(path, "r", encoding="utf-8") as f:
        try:
            d = json.load(f)
        except json.JSONDecodeError:
            d = {}
    if "teams" not in d: d["teams"] = {}
    if "memberships" not in d: d["memberships"] = {}
    return d

def _save(data: Dict[str, Any], path: str = DEFAULT_PATH) -> None:
    _ensure_path(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def _key(name: str) -> str:
    return name.strip().lower()

def create_team(name: str, owner_id: int, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    data = _load(path)
    k = _key(name)
    if k in data["teams"]:
        # لو موجود نخلي المالك زي ما هو
        return data
    data["teams"][k] = {
        "name": name.strip(),
        "owner_id": int(owner_id),
        "members": [int(owner_id)],
        "pending": []
    }
    data["memberships"][str(owner_id)] = k
    _save(data, path)
    return data

def get_team(name: str, path: str = DEFAULT_PATH) -> Optional[Dict[str, Any]]:
    d = _load(path)
    return d["teams"].get(_key(name))

def request_join(name: str, user_id: int, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    d = _load(path)
    k = _key(name)
    if k not in d["teams"]:
        raise ValueError("TEAM_NOT_FOUND")
    t = d["teams"][k]
    uid = int(user_id)
    if uid in t["members"]:
        raise ValueError("ALREADY_MEMBER")
    if uid in t["pending"]:
        # موجود طلب قديم
        return d
    t["pending"].append(uid)
    _save(d, path)
    return d

def approve(name: str, user_id: int, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    d = _load(path)
    k = _key(name)
    if k not in d["teams"]:
        raise ValueError("TEAM_NOT_FOUND")
    t = d["teams"][k]
    uid = int(user_id)
    if uid in t["pending"]:
        t["pending"].remove(uid)
    if uid not in t["members"]:
        t["members"].append(uid)
    d["memberships"][str(uid)] = k
    _save(d, path)
    return d

def deny(name: str, user_id: int, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    d = _load(path)
    k = _key(name)
    if k not in d["teams"]:
        raise ValueError("TEAM_NOT_FOUND")
    t = d["teams"][k]
    uid = int(user_id)
    if uid in t["pending"]:
        t["pending"].remove(uid)
    _save(d, path)
    return d

def my_team(user_id: int, path: str = DEFAULT_PATH) -> Optional[Dict[str, Any]]:
    d = _load(path)
    k = d["memberships"].get(str(user_id))
    if not k: return None
    return d["teams"].get(k)
