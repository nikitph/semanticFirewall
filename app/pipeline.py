from __future__ import annotations

import json

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
    ProposeSuccessResponse,
)
from app.storage import Storage


class Pipeline:
    def __init__(self, storage: Storage, canonicalizer: Canonicalizer):
        self.storage = storage
        self.canonicalizer = canonicalizer

    def process_draft(self, draft_json: str) -> ProposeSuccessResponse:
        draft_hash = sha256_hex(draft_json)
        try:
            draft = self._gate_1_parse(draft_json)
            chunk = self.storage.get_chunk(draft.source_chunk_id)
            if chunk is None:
                raise Gate2SchemaException(
                    "Unknown source_chunk_id",
                    {"source_chunk_id": draft.source_chunk_id},
                )

            span_refs = ground_quotes(draft.quoted_spans, chunk.text)
            for span in span_refs:
                assert chunk.text[span.start_index : span.end_index] == span.quote

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
            self.storage.log_audit_event(
                draft_hash=draft_hash,
                status="rejected",
                failed_gate=exc.gate_number,
                reason=exc.reason,
                details=exc.details,
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
