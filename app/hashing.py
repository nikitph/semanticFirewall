from __future__ import annotations

import hashlib
import json
from typing import Any

from app.models import CanonicalClaim, SpanRef


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def claim_id_for(canonical_claim: CanonicalClaim) -> str:
    return sha256_hex(canonical_json(canonical_claim.model_dump(exclude_none=True)))


def support_id_for(claim_id: str, source_chunk_id: str, span_refs: list[SpanRef]) -> str:
    support_payload = {
        "claim_id": claim_id,
        "source_chunk_id": source_chunk_id,
        "span_refs": [
            {
                "start_index": span.start_index,
                "end_index": span.end_index,
                "quote": span.quote,
            }
            for span in span_refs
        ],
    }
    return sha256_hex(canonical_json(support_payload))
