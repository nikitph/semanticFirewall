from __future__ import annotations

import json

from app.models import Chunk


def test_same_draft_is_idempotent_for_claim_and_support(storage, pipeline):
    storage.upsert_chunk(Chunk(chunk_id="chunk-1", text="Net revenue was $4M in FY2024."))
    draft_json = json.dumps(
        {
            "content": "Net revenue was $4M in FY2024.",
            "source_chunk_id": "chunk-1",
            "quoted_spans": ["Net revenue was $4M in FY2024"],
        }
    )

    first = pipeline.process_draft(draft_json)
    second = pipeline.process_draft(draft_json)

    assert first.claim_id == second.claim_id
    assert first.support_id == second.support_id
    with storage.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM supports").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] == 2
