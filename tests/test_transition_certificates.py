from __future__ import annotations

import json

import pytest

from app.exceptions import GateException
from app.hashing import sha256_hex
from app.models import Chunk


def test_committed_proposal_emits_transition_certificate(storage, pipeline):
    storage.upsert_chunk(Chunk(chunk_id="chunk-1", text="Revenue was $3M."))
    draft_json = json.dumps(
        {
            "content": "Revenue was $3M.",
            "source_chunk_id": "chunk-1",
            "quoted_spans": ["Revenue was $3M"],
        }
    )

    response = pipeline.process_draft(draft_json)
    certificates = storage.get_transition_certificates()

    assert len(certificates) == 1
    certificate = certificates[0]
    assert certificate.status == "committed"
    assert certificate.proposal_hash == sha256_hex(draft_json)
    assert certificate.claim_id == response.claim_id
    assert certificate.support_id == response.support_id
    assert certificate.pre_state_hash != certificate.post_state_hash
    assert [(gate.gate_number, gate.status) for gate in certificate.gate_results] == [
        (1, "passed"),
        (2, "passed"),
        (3, "passed"),
        (4, "passed"),
        (5, "passed"),
    ]


def test_rejected_proposal_emits_certificate_without_state_mutation(storage, pipeline):
    storage.upsert_chunk(Chunk(chunk_id="chunk-1", text="Revenue was $3M."))
    draft_json = json.dumps(
        {
            "content": "Revenue was $4M.",
            "source_chunk_id": "chunk-1",
            "quoted_spans": ["Revenue was $4M"],
        }
    )

    with pytest.raises(GateException):
        pipeline.process_draft(draft_json)

    certificates = storage.get_transition_certificates()
    assert len(certificates) == 1
    certificate = certificates[0]
    assert certificate.status == "rejected"
    assert certificate.claim_id is None
    assert certificate.support_id is None
    assert certificate.pre_state_hash == certificate.post_state_hash
    assert [(gate.gate_number, gate.status) for gate in certificate.gate_results] == [
        (1, "passed"),
        (2, "passed"),
        (3, "failed"),
    ]
