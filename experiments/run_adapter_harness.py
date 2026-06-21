from __future__ import annotations

import json
from pathlib import Path

from app.adapter_harness import GeneratorMetrics, run_generator_harness
from app.canonicalization import RuleCanonicalizer
from app.models import Chunk
from app.pipeline import Pipeline
from app.proposals import (
    HumanProposalGenerator,
    LLMStructuredProposalGenerator,
    OpenIEProposalGenerator,
    RuleProposalGenerator,
    evidence_draft_json,
)
from app.storage import Storage


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "adapter_harness.db"
REPORT_PATH = ROOT / "adapter_harness_report.md"


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    chunks = [Chunk.model_validate(item) for item in _load_json(ROOT / "sample_chunks.json")]
    storage = Storage(str(DB_PATH))
    storage.init_db()
    for chunk in chunks:
        storage.upsert_chunk(chunk)

    pipeline = Pipeline(storage=storage, canonicalizer=RuleCanonicalizer())
    rows = run_generator_harness(
        chunks=chunks,
        generators=_generators(),
        pipeline=pipeline,
    )

    _print_table(rows)
    _write_report(rows, storage)
    print(f"\nWrote {REPORT_PATH}")


def _generators():
    llm_structured = LLMStructuredProposalGenerator(
        {
            "chunk-1": [
                evidence_draft_json(
                    "Net revenue was $4M in FY2024.",
                    "chunk-1",
                    ["Net revenue was $4M in FY2024"],
                ),
                evidence_draft_json(
                    "Net revenue was $4M in FY2024.",
                    "chunk-1",
                    ["Net revenue was $4M in FY2024"],
                ),
                evidence_draft_json(
                    "Net revenue was $5M in FY2024.",
                    "chunk-1",
                    ["Net revenue was $5M"],
                ),
            ],
            "chunk-2": ["{not-json"],
            "chunk-3": [
                evidence_draft_json(
                    'The CEO said "Growth" was the theme.',
                    "chunk-3",
                    ['said "Growth"'],
                )
            ],
            "chunk-4": [
                evidence_draft_json(
                    "The company reported net revenue of $4M in FY2024.",
                    "missing-chunk",
                    ["company reported"],
                )
            ],
        },
        cost_per_proposal_usd=0.002,
    )

    openie = OpenIEProposalGenerator(
        {
            "chunk-1": [
                evidence_draft_json(
                    "Net revenue was $4M in FY2024.",
                    "chunk-1",
                    ["Net revenue was $4M"],
                )
            ],
            "chunk-2": [
                evidence_draft_json(
                    "Net revenue was $4M after adjustments.",
                    "chunk-2",
                    ["Net revenue was $4M"],
                )
            ],
            "chunk-3": [
                evidence_draft_json(
                    "The CEO said contraction was the theme.",
                    "chunk-3",
                    ["said contraction was the theme"],
                )
            ],
            "chunk-4": [
                evidence_draft_json(
                    "The company reported net revenue of $4M in FY2024.",
                    "chunk-4",
                    ["company reported...FY2024"],
                )
            ],
        }
    )

    return [
        HumanProposalGenerator(ROOT / "human_proposals.json"),
        RuleProposalGenerator(),
        llm_structured,
        openie,
    ]


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _print_table(rows: list[GeneratorMetrics]) -> None:
    print(_header())
    print("--- | --- | --- | --- | --- | --- | --- | --- | --- | ---")
    for row in rows:
        print(_row(row))


def _write_report(rows: list[GeneratorMetrics], storage: Storage) -> None:
    graph = storage.get_graph_summary()
    audit_count = _audit_count(storage)
    certificate_count = len(storage.get_transition_certificates())
    lines = [
        "# Adapter Harness Report",
        "",
        "## Summary",
        (
            "This experiment treats extractors as untrusted proposal generators. "
            "Each adapter emits draft JSON into the same Grounding Firewall runtime."
        ),
        "",
        f"- committed blackboard claims: {graph.claim_count}",
        f"- committed supports: {graph.support_count}",
        f"- audit events: {audit_count}",
        f"- transition certificates: {certificate_count}",
        "",
        "## Generator Metrics",
        _header(),
        "--- | --- | --- | --- | --- | --- | --- | --- | --- | ---",
    ]
    lines.extend(_row(row) for row in rows)
    lines.extend(
        [
            "",
            "## Runtime Contract",
            "- Same Gate 1 parsing path for every adapter.",
            "- Same Gate 2 source-reference validation for every adapter.",
            "- Same Gate 3 deterministic grounding for every adapter.",
            "- Same ClaimID and SupportID hashing for every accepted proposal.",
            "- Same append-only audit log for accepted and rejected proposals.",
            "- Same provenance query surface after commit.",
            "- Same Transition Admissibility Certificate shape for every proposal attempt.",
            "",
            "## Framing",
            "NLP proposes. Transactional Cognition commits.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def _header() -> str:
    return (
        "generator | proposals | committed | rejected_gate_1 | rejected_gate_2 | "
        "rejected_gate_3 | unique_claims | duplicate_supports | cost_usd | latency_ms"
    )


def _row(row: GeneratorMetrics) -> str:
    return (
        f"{row.generator} | {row.proposals} | {row.committed} | {row.rejected_gate_1} | "
        f"{row.rejected_gate_2} | {row.rejected_gate_3} | {row.unique_claims} | "
        f"{row.duplicate_supports} | {row.cost_usd:.4f} | {row.latency_ms:.2f}"
    )


def _audit_count(storage: Storage) -> int:
    with storage.connect() as connection:
        return connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]


if __name__ == "__main__":
    main()
