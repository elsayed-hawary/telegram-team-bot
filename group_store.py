# group_store.py
import os, json, secrets, string
from typing import Dict, Any, Optional, List

DEFAULT_PATH = os.getenv("GROUPS_PATH", "./data/groups.json")

def _ensure_path(path: str) -> None:
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"groups": {}}, f, ensure_ascii=False)

def _load(path: str = DEFAULT_PATH) -> Dict[str, Any]:
    _ensure_path(path)
    with open(path, "r", encoding="utf-8") as f:
        try: d = json.load(f)
        except json.JSONDecodeError: d = {}
    d.setdefault("groups", {})
    return d

def _save(d: Dict[str, Any], path: str = DEFAULT_PATH) -> None:
    _ensure_path(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def _gen_numeric_id(length: int = 6) -> str:
    digits = string.digits
    return "".join(secrets.choice(digits) for _ in range(length))

def create_group(name: str, owner_user_id: int, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    d = _load(path)
    # كل شخص يملك مجموعة واحدة فقط
    for g in d["groups"].values():
        if g["owner_user_id"] == int(owner_user_id):
            raise ValueError("ALREADY_OWNER")
    while True:
        gid = _gen_numeric_id(6)  # أرقام فقط
        if gid not in d["groups"]:
            break
    d["groups"][gid] = {
        "group_id": gid,
        "name": name.strip(),
        "owner_user_id": int(owner_user_id),
        "members": [int(owner_user_id)],
        "pending": []
    }
    _save(d, path)
    return d["groups"][gid]

def get_group(group_id: str, path: str = DEFAULT_PATH) -> Optional[Dict[str, Any]]:
    return _load(path)["groups"].get(group_id.strip())

def is_owner(group_id: str, user_id: int, path: str = DEFAULT_PATH) -> bool:
    g = get_group(group_id, path)
    return bool(g and g["owner_user_id"] == int(user_id))

def request_join(group_id: str, user_id: int, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    d = _load(path)
    gid = group_id.strip()
    g = d["groups"].get(gid)
    if not g: raise ValueError("GROUP_NOT_FOUND")
    uid = int(user_id)
    if uid in g["members"]: raise ValueError("ALREADY_MEMBER")
    if uid not in g["pending"]: g["pending"].append(uid)
    _save(d, path)
    return g

def approve_join(group_id: str, user_id: int, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    d = _load(path)
    gid = group_id.strip()
    g = d["groups"].get(gid)
    if not g: raise ValueError("GROUP_NOT_FOUND")
    uid = int(user_id)
    if uid in g["pending"]: g["pending"].remove(uid)
    if uid not in g["members"]: g["members"].append(uid)
    _save(d, path)
    return g

def deny_join(group_id: str, user_id: int, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    d = _load(path)
    gid = group_id.strip()
    g = d["groups"].get(gid)
    if not g: raise ValueError("GROUP_NOT_FOUND")
    uid = int(user_id)
    if uid in g["pending"]: g["pending"].remove(uid)
    _save(d, path)
    return g

def add_member(group_id: str, user_id: int, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    d = _load(path)
    gid = group_id.strip()
    g = d["groups"].get(gid)
    if not g: raise ValueError("GROUP_NOT_FOUND")
    uid = int(user_id)
    if uid not in g["members"]: g["members"].append(uid)
    if uid in g["pending"]: g["pending"].remove(uid)
    _save(d, path)
    return g

def remove_member(group_id: str, user_id: int, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    d = _load(path)
    gid = group_id.strip()
    g = d["groups"].get(gid)
    if not g: raise ValueError("GROUP_NOT_FOUND")
    uid = int(user_id)
    if uid in g["members"] and uid != g["owner_user_id"]:
        g["members"].remove(uid)
    if uid in g["pending"]:
        g["pending"].remove(uid)
    _save(d, path)
    return g

def my_groups(user_id: int, path: str = DEFAULT_PATH) -> List[Dict[str, Any]]:
    d = _load(path)
    uid = int(user_id)
    return [g for g in d["groups"].values() if uid in g.get("members", [])]

def owner_group(user_id: int, path: str = DEFAULT_PATH) -> Optional[Dict[str, Any]]:
    d = _load(path)
    for g in d["groups"].values():
        if g["owner_user_id"] == int(user_id):
            return g
    return None

def list_members(group_id: str, path: str = DEFAULT_PATH) -> List[int]:
    g = get_group(group_id, path)
    return list(g.get("members", [])) if g else []