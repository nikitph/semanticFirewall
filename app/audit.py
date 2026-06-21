from __future__ import annotations

from typing import Any

from app.hashing import canonical_json, sha256_hex


def audit_event_id(timestamp: str, draft_hash: str | None, status: str, counter_seed: str) -> str:
    return sha256_hex(
        canonical_json(
            {
                "timestamp": timestamp,
                "draft_hash": draft_hash,
                "status": status,
                "counter_seed": counter_seed,
            }
        )
    )


def safe_details(details: dict[str, Any] | None) -> dict[str, Any]:
    return details or {}
