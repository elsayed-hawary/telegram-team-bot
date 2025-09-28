# team_store.py
import os, json, random, string
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
    d.setdefault("teams", {})
    d.setdefault("memberships", {})
    return d

def _save(data: Dict[str, Any], path: str = DEFAULT_PATH) -> None:
    _ensure_path(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def _gen_id(k: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(random.choice(alphabet) for _ in range(k))

# --------- واجهة بالـ Team ID ---------

def new_team(owner_id: int, path: str = DEFAULT_PATH) -> str:
    """ينشئ Team جديد بمعرّف تلقائي ويُسجّل المالك عضوًا."""
    data = _load(path)
    while True:
        tid = _gen_id()
        if tid not in data["teams"]:
            break
    data["teams"][tid] = {
        "id": tid,
        "name": "",                 # يُعيَّن لاحقًا بـ set_team_name
        "owner_id": int(owner_id),
        "members": [int(owner_id)],
        "pending": []
    }
    data["memberships"][str(owner_id)] = tid
    _save(data, path)
    return tid

def set_team_name(team_id: str, name: str, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    data = _load(path)
    t = data["teams"].get(team_id)
    if not t:
        raise ValueError("TEAM_NOT_FOUND")
    t["name"] = name.strip()
    _save(data, path)
    return t

def get_team_by_id(team_id: str, path: str = DEFAULT_PATH) -> Optional[Dict[str, Any]]:
    return _load(path)["teams"].get(team_id)

def request_join(team_id: str, user_id: int, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    d = _load(path)
    t = d["teams"].get(team_id)
    if not t:
        raise ValueError("TEAM_NOT_FOUND")
    uid = int(user_id)
    if uid in t["members"]:
        raise ValueError("ALREADY_MEMBER")
    if uid not in t["pending"]:
        t["pending"].append(uid)
    _save(d, path)
    return t

def approve(team_id: str, user_id: int, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    d = _load(path)
    t = d["teams"].get(team_id)
    if not t:
        raise ValueError("TEAM_NOT_FOUND")
    uid = int(user_id)
    if uid in t["pending"]:
        t["pending"].remove(uid)
    if uid not in t["members"]:
        t["members"].append(uid)
    d["memberships"][str(uid)] = team_id
    _save(d, path)
    return t

def deny(team_id: str, user_id: int, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    d = _load(path)
    t = d["teams"].get(team_id)
    if not t:
        raise ValueError("TEAM_NOT_FOUND")
    uid = int(user_id)
    if uid in t["pending"]:
        t["pending"].remove(uid)
    _save(d, path)
    return t

def my_team(user_id: int, path: str = DEFAULT_PATH) -> Optional[Dict[str, Any]]:
    d = _load(path)
    tid = d["memberships"].get(str(user_id))
    if not tid:
        return None
    return d["teams"].get(tid)