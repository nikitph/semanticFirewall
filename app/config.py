from __future__ import annotations

import os


DEFAULT_DB_PATH = "./grounding_firewall.db"


def get_db_path() -> str:
    return os.environ.get("GROUNDING_FIREWALL_DB_PATH", DEFAULT_DB_PATH)
