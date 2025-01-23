import json
import os
from typing import Dict, Optional

SESSION_FILE = "session_store.json"

def load_cookies(username: str) -> Optional[Dict[str, str]]:
    """
    ユーザー名をキーに、session_store.json からクッキー情報を読み込み。
    見つからない場合は None を返す。
    """
    if not os.path.exists(SESSION_FILE):
        return None

    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            store = json.load(f)
        cookies = store.get(username)
        if isinstance(cookies, dict):
            return cookies
        else:
            return None
    except Exception:
        return None

def save_cookies(username: str, cookies: Dict[str, str]) -> None:
    """
    ユーザー名をキーに、クッキー辞書を session_store.json に上書き保存。
    """
    store = {}
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                store = json.load(f)
        except Exception:
            # JSONが壊れていた場合などは新規作成
            store = {}

    store[username] = cookies
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
