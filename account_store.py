# account_store.py
import os, json, string, secrets
from typing import Dict, Any, Optional

DEFAULT_PATH = os.getenv("ACCOUNTS_PATH", "./data/accounts.json")

def _ensure_path(path: str) -> None:
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"accounts": {}, "by_user": {}}, f, ensure_ascii=False)

def _load(path: str = DEFAULT_PATH) -> Dict[str, Any]:
    _ensure_path(path)
    with open(path, "r", encoding="utf-8") as f:
        try: d = json.load(f)
        except json.JSONDecodeError: d = {}
    d.setdefault("accounts", {})
    d.setdefault("by_user", {})
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

def get_account_by_user(user_id: int, path: str = DEFAULT_PATH) -> Optional[Dict[str, Any]]:
    d = _load(path)
    acc_id = d["by_user"].get(str(user_id))
    return d["accounts"].get(acc_id) if acc_id else None

def create_or_update_account(user_id: int, name: str, path: str = DEFAULT_PATH) -> Dict[str, Any]:
    d = _load(path)
    acc_id = d["by_user"].get(str(user_id))
    if not acc_id:
        while True:
            acc_id = _gen_id("U")
            if acc_id not in d["accounts"]:
                break
        d["by_user"][str(user_id)] = acc_id
        d["accounts"][acc_id] = {"account_id": acc_id, "user_id": int(user_id), "name": name}
    else:
        d["accounts"][acc_id]["name"] = name
    _save(d, path)
    return d["accounts"][acc_id]