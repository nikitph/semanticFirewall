from __future__ import annotations

import json

import pytest

from app.canonicalization import MockCanonicalizer
from app.exceptions import GateException
from app.models import Chunk
from app.pipeline import Pipeline


class BadCanonicalizer:
    def canonicalize(self, content: str):
        return {"subject": "bad", "predicate": "has spaces", "object": content}


@pytest.mark.parametrize(
    ("draft_json", "expected_gate"),
    [
        ("{not-json", 1),
        (json.dumps({"content": "x", "source_chunk_id": "chunk-1"}), 1),
    ],
)
def test_gate_1_failures_are_audited(storage, draft_json, expected_gate):
    pipeline = Pipeline(storage=storage, canonicalizer=MockCanonicalizer())
    storage.upsert_chunk(Chunk(chunk_id="chunk-1", text="Alpha."))

    with pytest.raises(GateException) as exc_info:
        pipeline.process_draft(draft_json)

    assert exc_info.value.gate_number == expected_gate
    assert _count(storage, "claims") == 0
    assert _count(storage, "supports") == 0
    assert _count(storage, "audit_events") == 1


def test_gate_2_unknown_source_chunk_id(storage, pipeline):
    draft = {
        "content": "Alpha.",
        "source_chunk_id": "missing",
        "quoted_spans": ["Alpha"],
    }

    with pytest.raises(GateException) as exc_info:
        pipeline.process_draft(json.dumps(draft))

    assert exc_info.value.gate_number == 2
    assert _count(storage, "claims") == 0
    assert _count(storage, "supports") == 0
    assert _count(storage, "audit_events") == 1


def test_gate_3_fabricated_quote(storage, pipeline):
    storage.upsert_chunk(Chunk(chunk_id="chunk-1", text="Revenue was $3M."))
    draft = {
        "content": "Revenue was $4M.",
        "source_chunk_id": "chunk-1",
        "quoted_spans": ["Revenue was $4M"],
    }

    with pytest.raises(GateException) as exc_info:
        pipeline.process_draft(json.dumps(draft))

    assert exc_info.value.gate_number == 3
    assert _count(storage, "claims") == 0
    assert _count(storage, "supports") == 0
    assert _count(storage, "audit_events") == 1


def test_gate_4_bad_canonicalizer_output(storage):
    storage.upsert_chunk(Chunk(chunk_id="chunk-1", text="Alpha."))
    pipeline = Pipeline(storage=storage, canonicalizer=BadCanonicalizer())
    draft = {
        "content": "Alpha.",
        "source_chunk_id": "chunk-1",
        "quoted_spans": ["Alpha"],
    }

    with pytest.raises(GateException) as exc_info:
        pipeline.process_draft(json.dumps(draft))

    assert exc_info.value.gate_number == 4
    assert _count(storage, "claims") == 0
    assert _count(storage, "supports") == 0
    assert _count(storage, "audit_events") == 1


def _count(storage, table: str) -> int:
    with storage.connect() as connection:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
