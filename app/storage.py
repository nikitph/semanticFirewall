from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.audit import audit_event_id
from app.config import get_db_path
from app.hashing import canonical_json, sha256_hex
from app.models import (
    CanonicalClaim,
    ClaimProvenanceResponse,
    Chunk,
    EvidenceClaim,
    EvidenceSupport,
    GateResult,
    GraphClaimSummary,
    GraphResponse,
    ProvenanceSupport,
    SpanRef,
    TransitionAdmissibilityCertificate,
)


class Storage:
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or get_db_path()
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def init_db(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    text_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    canonical_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS supports (
                    support_id TEXT PRIMARY KEY,
                    claim_id TEXT NOT NULL,
                    source_chunk_id TEXT NOT NULL,
                    span_refs_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (claim_id) REFERENCES claims(claim_id),
                    FOREIGN KEY (source_chunk_id) REFERENCES chunks(chunk_id)
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    draft_hash TEXT,
                    status TEXT NOT NULL,
                    failed_gate INTEGER,
                    reason TEXT,
                    details_json TEXT,
                    claim_id TEXT,
                    support_id TEXT
                );

                CREATE TABLE IF NOT EXISTS transition_certificates (
                    certificate_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    proposal_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    pre_state_hash TEXT NOT NULL,
                    post_state_hash TEXT NOT NULL,
                    gate_results_json TEXT NOT NULL,
                    claim_id TEXT,
                    support_id TEXT
                );
                """
            )

    def upsert_chunk(self, chunk: Chunk) -> None:
        now = _utc_now()
        text_hash = sha256_hex(chunk.text)
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO chunks (chunk_id, text, text_hash, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(chunk_id) DO UPDATE SET
                    text = excluded.text,
                    text_hash = excluded.text_hash
                """,
                (chunk.chunk_id, chunk.text, text_hash, now),
            )

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT chunk_id, text FROM chunks WHERE chunk_id = ?",
                (chunk_id,),
            ).fetchone()
        if row is None:
            return None
        return Chunk(chunk_id=row["chunk_id"], text=row["text"])

    def insert_claim_if_absent(self, claim: EvidenceClaim, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            INSERT OR IGNORE INTO claims (claim_id, canonical_json, created_at)
            VALUES (?, ?, ?)
            """,
            (
                claim.claim_id,
                canonical_json(claim.canonical_claim.model_dump(exclude_none=True)),
                _utc_now(),
            ),
        )

    def insert_support_if_absent(
        self, support: EvidenceSupport, connection: sqlite3.Connection
    ) -> None:
        span_refs_json = canonical_json(
            [span.model_dump() for span in support.span_refs]
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO supports
                (support_id, claim_id, source_chunk_id, span_refs_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                support.support_id,
                support.claim_id,
                support.source_chunk_id,
                span_refs_json,
                _utc_now(),
            ),
        )

    def log_audit_event(
        self,
        *,
        draft_hash: str | None,
        status: str,
        failed_gate: int | None = None,
        reason: str | None = None,
        details: dict[str, Any] | None = None,
        claim_id: str | None = None,
        support_id: str | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        close_connection = connection is None
        active_connection = connection or self.connect()
        try:
            timestamp = _utc_now()
            row_count = active_connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
            event_id = audit_event_id(timestamp, draft_hash, status, str(row_count))
            active_connection.execute(
                """
                INSERT INTO audit_events (
                    event_id, timestamp, draft_hash, status, failed_gate, reason,
                    details_json, claim_id, support_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    timestamp,
                    draft_hash,
                    status,
                    failed_gate,
                    reason,
                    canonical_json(details or {}),
                    claim_id,
                    support_id,
                ),
            )
            if close_connection:
                active_connection.commit()
        finally:
            if close_connection:
                active_connection.close()

    def get_graph_summary(self) -> GraphResponse:
        with self.connect() as connection:
            claim_rows = connection.execute(
                "SELECT claim_id, canonical_json FROM claims ORDER BY claim_id"
            ).fetchall()
            support_rows = connection.execute(
                """
                SELECT support_id, claim_id, source_chunk_id, span_refs_json
                FROM supports
                ORDER BY support_id
                """
            ).fetchall()

        supports_by_claim: dict[str, list[EvidenceSupport]] = {}
        for row in support_rows:
            span_refs = [SpanRef.model_validate(item) for item in json.loads(row["span_refs_json"])]
            support = EvidenceSupport(
                support_id=row["support_id"],
                claim_id=row["claim_id"],
                source_chunk_id=row["source_chunk_id"],
                span_refs=span_refs,
            )
            supports_by_claim.setdefault(row["claim_id"], []).append(support)

        claims = []
        for row in claim_rows:
            canonical_claim = CanonicalClaim.model_validate(json.loads(row["canonical_json"]))
            supports = supports_by_claim.get(row["claim_id"], [])
            claims.append(
                GraphClaimSummary(
                    claim_id=row["claim_id"],
                    canonical_claim=canonical_claim,
                    support_count=len(supports),
                    supports=supports,
                )
            )

        return GraphResponse(
            claim_count=len(claim_rows),
            support_count=len(support_rows),
            claims=claims,
        )

    def get_claim_provenance(self, claim_id: str) -> ClaimProvenanceResponse | None:
        with self.connect() as connection:
            claim_row = connection.execute(
                "SELECT claim_id, canonical_json FROM claims WHERE claim_id = ?",
                (claim_id,),
            ).fetchone()
            if claim_row is None:
                return None

            support_rows = connection.execute(
                """
                SELECT support_id, source_chunk_id, span_refs_json
                FROM supports
                WHERE claim_id = ?
                ORDER BY support_id
                """,
                (claim_id,),
            ).fetchall()

        supports = []
        for row in support_rows:
            span_refs = [SpanRef.model_validate(item) for item in json.loads(row["span_refs_json"])]
            supports.append(
                ProvenanceSupport(
                    support_id=row["support_id"],
                    source_chunk_id=row["source_chunk_id"],
                    span_refs=span_refs,
                )
            )

        return ClaimProvenanceResponse(
            claim_id=claim_row["claim_id"],
            canonical_claim=CanonicalClaim.model_validate(json.loads(claim_row["canonical_json"])),
            support_count=len(supports),
            supports=supports,
        )

    def compute_blackboard_state_hash(self, connection: sqlite3.Connection | None = None) -> str:
        close_connection = connection is None
        active_connection = connection or self.connect()
        try:
            chunks = [
                {
                    "chunk_id": row["chunk_id"],
                    "text_hash": row["text_hash"],
                }
                for row in active_connection.execute(
                    "SELECT chunk_id, text_hash FROM chunks ORDER BY chunk_id"
                ).fetchall()
            ]
            claims = [
                {
                    "claim_id": row["claim_id"],
                    "canonical_json": row["canonical_json"],
                }
                for row in active_connection.execute(
                    "SELECT claim_id, canonical_json FROM claims ORDER BY claim_id"
                ).fetchall()
            ]
            supports = [
                {
                    "support_id": row["support_id"],
                    "claim_id": row["claim_id"],
                    "source_chunk_id": row["source_chunk_id"],
                    "span_refs_json": row["span_refs_json"],
                }
                for row in active_connection.execute(
                    """
                    SELECT support_id, claim_id, source_chunk_id, span_refs_json
                    FROM supports
                    ORDER BY support_id
                    """
                ).fetchall()
            ]
            return sha256_hex(
                canonical_json(
                    {
                        "chunks": chunks,
                        "claims": claims,
                        "supports": supports,
                    }
                )
            )
        finally:
            if close_connection:
                active_connection.close()

    def insert_transition_certificate(
        self,
        certificate: TransitionAdmissibilityCertificate,
        connection: sqlite3.Connection,
    ) -> None:
        connection.execute(
            """
            INSERT INTO transition_certificates (
                certificate_id, timestamp, proposal_hash, status, pre_state_hash,
                post_state_hash, gate_results_json, claim_id, support_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                certificate.certificate_id,
                _utc_now(),
                certificate.proposal_hash,
                certificate.status,
                certificate.pre_state_hash,
                certificate.post_state_hash,
                canonical_json([gate.model_dump(exclude_none=True) for gate in certificate.gate_results]),
                certificate.claim_id,
                certificate.support_id,
            ),
        )

    def get_transition_certificates(self) -> list[TransitionAdmissibilityCertificate]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT certificate_id, proposal_hash, status, pre_state_hash, post_state_hash,
                    gate_results_json, claim_id, support_id
                FROM transition_certificates
                ORDER BY timestamp, certificate_id
                """
            ).fetchall()

        return [
            TransitionAdmissibilityCertificate(
                certificate_id=row["certificate_id"],
                proposal_hash=row["proposal_hash"],
                status=row["status"],
                pre_state_hash=row["pre_state_hash"],
                post_state_hash=row["post_state_hash"],
                gate_results=[
                    GateResult.model_validate(item) for item in json.loads(row["gate_results_json"])
                ],
                claim_id=row["claim_id"],
                support_id=row["support_id"],
            )
            for row in rows
        ]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
