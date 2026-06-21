from __future__ import annotations

import json

from app.models import Chunk


def test_pipeline_commits_valid_draft(storage, pipeline):
    storage.upsert_chunk(Chunk(chunk_id="chunk-1", text="Net revenue was $4M in FY2024."))
    draft = {
        "content": "Net revenue was $4M in FY2024.",
        "source_chunk_id": "chunk-1",
        "quoted_spans": ["Net revenue was $4M in FY2024"],
    }

    response = pipeline.process_draft(json.dumps(draft))
    graph = storage.get_graph_summary()

    assert response.status == "committed"
    assert graph.claim_count == 1
    assert graph.support_count == 1
    assert graph.claims[0].support_count == 1
    with storage.connect() as connection:
        audit_count = connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        status = connection.execute("SELECT status FROM audit_events").fetchone()[0]
    assert audit_count == 1
    assert status == "committed"
