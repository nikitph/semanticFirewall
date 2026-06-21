from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class SpanRef(StrictBaseModel):
    start_index: int = Field(description="Inclusive Python character index in raw chunk text.")
    end_index: int = Field(description="Exclusive Python character index in raw chunk text.")
    quote: str = Field(description="Exact raw substring from chunk.text[start_index:end_index].")

    @field_validator("start_index", "end_index")
    @classmethod
    def non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Index must be non-negative.")
        return value


class Chunk(StrictBaseModel):
    chunk_id: str
    text: str


class IngestRequest(StrictBaseModel):
    chunks: list[Chunk]


class EvidenceDraft(StrictBaseModel):
    content: str = Field(description="Natural-language claim extracted by an untrusted LLM.")
    source_chunk_id: str = Field(description="Chunk ID from which the evidence allegedly came.")
    quoted_spans: list[str] = Field(
        description="Quoted source substrings. Use '...' for intentionally discontiguous quotes."
    )

    @field_validator("quoted_spans")
    @classmethod
    def non_empty_spans(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("quoted_spans must contain at least one quote.")
        for span in value:
            if not span or not span.strip():
                raise ValueError("quoted_spans cannot contain empty strings.")
        return value


class ProposeRequest(StrictBaseModel):
    draft_json: str = Field(description="Raw JSON string emitted by an untrusted LLM.")


class CanonicalClaim(StrictBaseModel):
    subject: str
    predicate: str
    object: str
    temporal_bound: str | None = None

    @field_validator("subject", "predicate", "object")
    @classmethod
    def required_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Canonical fields cannot be empty.")
        return value.strip()

    @field_validator("predicate")
    @classmethod
    def normalize_predicate_shape(cls, value: str) -> str:
        value = value.strip().lower()
        if " " in value:
            raise ValueError("predicate must be a single normalized relation token.")
        return value


class EvidenceClaim(StrictBaseModel):
    claim_id: str
    canonical_claim: CanonicalClaim


class EvidenceSupport(StrictBaseModel):
    support_id: str
    claim_id: str
    source_chunk_id: str
    span_refs: list[SpanRef]


class ProposeSuccessResponse(StrictBaseModel):
    status: Literal["committed"]
    claim_id: str
    support_id: str
    canonical_claim: CanonicalClaim
    provenance_spans: list[SpanRef]


class ProposeFailureResponse(StrictBaseModel):
    status: Literal["rejected"]
    failed_gate: int
    reason: str
    details: dict[str, Any] | None = None


class GraphClaimSummary(StrictBaseModel):
    claim_id: str
    canonical_claim: CanonicalClaim
    support_count: int
    supports: list[EvidenceSupport]


class GraphResponse(StrictBaseModel):
    claim_count: int
    support_count: int
    claims: list[GraphClaimSummary]


class ProvenanceSupport(StrictBaseModel):
    support_id: str
    source_chunk_id: str
    span_refs: list[SpanRef]


class ClaimProvenanceResponse(StrictBaseModel):
    claim_id: str
    canonical_claim: CanonicalClaim
    support_count: int
    supports: list[ProvenanceSupport]


class GateResult(StrictBaseModel):
    gate_number: int
    gate_name: str
    status: Literal["passed", "failed"]
    reason: str | None = None
    details: dict[str, Any] | None = None


class TransitionAdmissibilityCertificate(StrictBaseModel):
    certificate_id: str
    proposal_hash: str
    status: Literal["committed", "rejected"]
    pre_state_hash: str
    post_state_hash: str
    gate_results: list[GateResult]
    claim_id: str | None = None
    support_id: str | None = None
