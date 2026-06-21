from __future__ import annotations

from app.adapter_harness import run_generator_harness
from app.canonicalization import RuleCanonicalizer
from app.models import Chunk
from app.pipeline import Pipeline
from app.proposals import FixtureProposalGenerator, RuleProposalGenerator, evidence_draft_json
from app.storage import Storage


def test_adapter_harness_routes_generators_through_same_commit_boundary(tmp_path):
    storage = Storage(str(tmp_path / "adapter.db"))
    storage.init_db()
    chunks = [
        Chunk(chunk_id="chunk-1", text="Revenue was $3M."),
        Chunk(chunk_id="chunk-2", text="Bookings increased in Q4."),
    ]
    for chunk in chunks:
        storage.upsert_chunk(chunk)

    pipeline = Pipeline(storage=storage, canonicalizer=RuleCanonicalizer())
    noisy_generator = FixtureProposalGenerator(
        name="NoisyFixtureGenerator",
        draft_json_by_chunk_id={
            "chunk-1": [
                evidence_draft_json("Revenue was $3M.", "chunk-1", ["Revenue was $3M"]),
                evidence_draft_json("Revenue was $3M.", "chunk-1", ["Revenue was $3M"]),
                evidence_draft_json("Revenue was $4M.", "chunk-1", ["Revenue was $4M"]),
            ],
            "chunk-2": [
                "{not-json",
                evidence_draft_json("Bookings increased in Q4.", "missing", ["Bookings increased"]),
            ],
        },
    )

    rows = run_generator_harness(
        chunks=chunks,
        generators=[RuleProposalGenerator(), noisy_generator],
        pipeline=pipeline,
    )

    rule_row = rows[0]
    noisy_row = rows[1]
    assert rule_row.proposals == 2
    assert rule_row.committed == 2
    assert rule_row.rejected_gate_1 == 0
    assert rule_row.rejected_gate_2 == 0
    assert rule_row.rejected_gate_3 == 0

    assert noisy_row.proposals == 5
    assert noisy_row.committed == 2
    assert noisy_row.duplicate_supports == 1
    assert noisy_row.rejected_gate_1 == 1
    assert noisy_row.rejected_gate_2 == 1
    assert noisy_row.rejected_gate_3 == 1

    with storage.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] == 7
        assert connection.execute("SELECT COUNT(*) FROM supports").fetchone()[0] == 3
