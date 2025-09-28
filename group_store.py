# group_store.py
import os, json, string, secrets
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

def _gen_id(prefix: str, length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return prefix + "".join(secrets.choice(alphabet) for _ in range(length))

def create_group(name: str, owner_user_id: int, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    d = _load(path)
    while True:
        gid = _gen_id("G")
        if gid not in d["groups"]:
            break
    d["groups"][gid] = {
        "group_id": gid,
        "name": name.strip(),
        "owner_user_id": int(owner_user_id),
        "members": [int(owner_user_id)]
    }
    _save(d, path)
    return d["groups"][gid]

def get_group(group_id: str, path: str = DEFAULT_PATH) -> Optional[Dict[str, Any]]:
    return _load(path)["groups"].get(group_id.strip().upper())

def add_member(group_id: str, user_id: int, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    d = _load(path)
    gid = group_id.strip().upper()
    if gid not in d["groups"]:
        raise ValueError("GROUP_NOT_FOUND")
    g = d["groups"][gid]
    uid = int(user_id)
    if uid not in g["members"]:
        g["members"].append(uid)
    _save(d, path)
    return g

def my_groups(user_id: int, path: str = DEFAULT_PATH) -> List[Dict[str, Any]]:
    d = _load(path)
    uid = int(user_id)
    return [g for g in d["groups"].values() if uid in g.get("members", [])]
