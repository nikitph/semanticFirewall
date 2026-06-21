from __future__ import annotations

import json
from typing import Literal
from uuid import uuid4

from pydantic import ValidationError

from app.canonicalization import Canonicalizer
from app.exceptions import (
    Gate1ParseException,
    Gate2SchemaException,
    Gate4CanonicalizationException,
    Gate5CommitException,
    GateException,
)
from app.grounding import ground_quotes
from app.hashing import claim_id_for, sha256_hex, support_id_for
from app.models import (
    CanonicalClaim,
    EvidenceClaim,
    EvidenceDraft,
    EvidenceSupport,
    GateResult,
    ProposeSuccessResponse,
    TransitionAdmissibilityCertificate,
)
from app.storage import Storage


class Pipeline:
    def __init__(self, storage: Storage, canonicalizer: Canonicalizer):
        self.storage = storage
        self.canonicalizer = canonicalizer

    def process_draft(self, draft_json: str) -> ProposeSuccessResponse:
        draft_hash = sha256_hex(draft_json)
        pre_state_hash = self.storage.compute_blackboard_state_hash()
        gate_results: list[GateResult] = []
        try:
            draft = self._gate_1_parse(draft_json)
            gate_results.append(_passed_gate(1))
            chunk = self.storage.get_chunk(draft.source_chunk_id)
            if chunk is None:
                raise Gate2SchemaException(
                    "Unknown source_chunk_id",
                    {"source_chunk_id": draft.source_chunk_id},
                )
            gate_results.append(_passed_gate(2))

            span_refs = ground_quotes(draft.quoted_spans, chunk.text)
            for span in span_refs:
                assert chunk.text[span.start_index : span.end_index] == span.quote
            gate_results.append(_passed_gate(3))

            try:
                canonical_claim = self.canonicalizer.canonicalize(draft.content)
                canonical_claim = CanonicalClaim.model_validate(canonical_claim.model_dump())
            except GateException:
                raise
            except Exception as exc:
                raise Gate4CanonicalizationException(
                    "Canonicalization failed.",
                    {"error": str(exc)},
                ) from exc
            gate_results.append(_passed_gate(4))

            claim_id = claim_id_for(canonical_claim)
            claim = EvidenceClaim(claim_id=claim_id, canonical_claim=canonical_claim)
            support_id = support_id_for(claim_id, draft.source_chunk_id, span_refs)
            support = EvidenceSupport(
                support_id=support_id,
                claim_id=claim_id,
                source_chunk_id=draft.source_chunk_id,
                span_refs=span_refs,
            )

            try:
                with self.storage.connect() as connection:
                    self.storage.insert_claim_if_absent(claim, connection)
                    self.storage.insert_support_if_absent(support, connection)
                    gate_results.append(_passed_gate(5))
                    post_state_hash = self.storage.compute_blackboard_state_hash(connection)
                    self.storage.insert_transition_certificate(
                        _certificate(
                            proposal_hash=draft_hash,
                            status="committed",
                            pre_state_hash=pre_state_hash,
                            post_state_hash=post_state_hash,
                            gate_results=gate_results,
                            claim_id=claim_id,
                            support_id=support_id,
                        ),
                        connection,
                    )
                    self.storage.log_audit_event(
                        draft_hash=draft_hash,
                        status="committed",
                        claim_id=claim_id,
                        support_id=support_id,
                        connection=connection,
                    )
            except Exception as exc:
                raise Gate5CommitException("Commit failed.", {"error": str(exc)}) from exc

            return ProposeSuccessResponse(
                status="committed",
                claim_id=claim_id,
                support_id=support_id,
                canonical_claim=canonical_claim,
                provenance_spans=span_refs,
            )
        except GateException as exc:
            _ensure_failed_gate(gate_results, exc)
            post_state_hash = self.storage.compute_blackboard_state_hash()
            with self.storage.connect() as connection:
                self.storage.insert_transition_certificate(
                    _certificate(
                        proposal_hash=draft_hash,
                        status="rejected",
                        pre_state_hash=pre_state_hash,
                        post_state_hash=post_state_hash,
                        gate_results=gate_results,
                    ),
                    connection,
                )
                self.storage.log_audit_event(
                    draft_hash=draft_hash,
                    status="rejected",
                    failed_gate=exc.gate_number,
                    reason=exc.reason,
                    details=exc.details,
                    connection=connection,
                )
            raise

    @staticmethod
    def _gate_1_parse(draft_json: str) -> EvidenceDraft:
        try:
            data = json.loads(draft_json)
            return EvidenceDraft.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            raise Gate1ParseException(
                "Draft JSON could not be parsed or validated.",
                {"error": str(exc)},
            ) from exc


GATE_NAMES = {
    1: "parse",
    2: "source_reference",
    3: "grounding",
    4: "canonicalization",
    5: "hash_and_commit",
}


def _passed_gate(gate_number: int) -> GateResult:
    return GateResult(
        gate_number=gate_number,
        gate_name=GATE_NAMES[gate_number],
        status="passed",
    )


def _failed_gate(exc: GateException) -> GateResult:
    return GateResult(
        gate_number=exc.gate_number,
        gate_name=GATE_NAMES.get(exc.gate_number, "unknown"),
        status="failed",
        reason=exc.reason,
        details=exc.details,
    )


def _ensure_failed_gate(gate_results: list[GateResult], exc: GateException) -> None:
    if any(gate.gate_number == exc.gate_number and gate.status == "failed" for gate in gate_results):
        return
    gate_results.append(_failed_gate(exc))


def _certificate(
    *,
    proposal_hash: str,
    status: Literal["committed", "rejected"],
    pre_state_hash: str,
    post_state_hash: str,
    gate_results: list[GateResult],
    claim_id: str | None = None,
    support_id: str | None = None,
) -> TransitionAdmissibilityCertificate:
    payload = {
        "certificate_nonce": uuid4().hex,
        "proposal_hash": proposal_hash,
        "status": status,
        "pre_state_hash": pre_state_hash,
        "post_state_hash": post_state_hash,
        "gate_results": [gate.model_dump(exclude_none=True) for gate in gate_results],
        "claim_id": claim_id,
        "support_id": support_id,
    }
    return TransitionAdmissibilityCertificate(
        certificate_id=sha256_hex(json.dumps(payload, sort_keys=True, default=str)),
        proposal_hash=proposal_hash,
        status=status,
        pre_state_hash=pre_state_hash,
        post_state_hash=post_state_hash,
        gate_results=gate_results,
        claim_id=claim_id,
        support_id=support_id,
    )
