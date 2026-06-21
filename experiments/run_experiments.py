from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.canonicalization import MockCanonicalizer
from app.exceptions import GateException
from app.models import Chunk
from app.pipeline import Pipeline
from app.storage import Storage


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "experiment.db"
REPORT_PATH = ROOT / "report.md"


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    storage = Storage(str(DB_PATH))
    storage.init_db()
    pipeline = Pipeline(storage=storage, canonicalizer=MockCanonicalizer())

    chunks = [Chunk.model_validate(item) for item in _load_json(ROOT / "sample_chunks.json")]
    for chunk in chunks:
        storage.upsert_chunk(chunk)

    cases = _load_json(ROOT / "sample_drafts.json")
    rows: list[dict[str, Any]] = []
    for case in cases:
        status = "committed"
        failed_gate = None
        try:
            pipeline.process_draft(json.dumps(case["draft"]))
        except GateException as exc:
            status = "rejected"
            failed_gate = exc.gate_number

        expected_gate = case["expected_gate"]
        passed = (expected_gate is None and status == "committed") or failed_gate == expected_gate
        rows.append(
            {
                "case_name": case["case_name"],
                "expected_gate": expected_gate,
                "actual_status": status,
                "failed_gate": failed_gate,
                "passed": passed,
            }
        )

    idempotence_ok = _run_idempotence_check(storage, pipeline)
    invariant_ok = _check_invariant(storage)
    _print_table(rows)
    _write_report(rows, storage, invariant_ok, idempotence_ok)
    print(f"\nWrote {REPORT_PATH}")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_idempotence_check(storage: Storage, pipeline: Pipeline) -> bool:
    before = _counts(storage)
    draft = {
        "content": "Net revenue was $4M in FY2024.",
        "source_chunk_id": "chunk-1",
        "quoted_spans": ["Net revenue was $4M in FY2024"],
    }
    first = pipeline.process_draft(json.dumps(draft))
    second = pipeline.process_draft(json.dumps(draft))
    after = _counts(storage)
    return (
        first.claim_id == second.claim_id
        and first.support_id == second.support_id
        and after["claims"] == before["claims"]
        and after["supports"] == before["supports"]
        and after["audit_events"] == before["audit_events"] + 2
    )


def _check_invariant(storage: Storage) -> bool:
    with storage.connect() as connection:
        rows = connection.execute(
            """
            SELECT c.text, s.span_refs_json
            FROM supports s
            JOIN chunks c ON c.chunk_id = s.source_chunk_id
            """
        ).fetchall()

    for row in rows:
        span_refs = json.loads(row["span_refs_json"])
        for span in span_refs:
            if row["text"][span["start_index"] : span["end_index"]] != span["quote"]:
                return False
    return True


def _counts(storage: Storage) -> dict[str, int]:
    with storage.connect() as connection:
        return {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("claims", "supports", "audit_events")
        }


def _print_table(rows: list[dict[str, Any]]) -> None:
    print("case_name | expected_gate | actual_status | failed_gate | passed")
    print("--- | --- | --- | --- | ---")
    for row in rows:
        print(
            f"{row['case_name']} | {row['expected_gate']} | {row['actual_status']} | "
            f"{row['failed_gate']} | {row['passed']}"
        )


def _write_report(
    rows: list[dict[str, Any]],
    storage: Storage,
    invariant_ok: bool,
    idempotence_ok: bool,
) -> None:
    total = len(rows)
    committed = sum(1 for row in rows if row["actual_status"] == "committed")
    rejected = total - committed
    rejection_by_gate = Counter(row["failed_gate"] for row in rows if row["failed_gate"] is not None)

    lines = [
        "# Grounding Firewall v1 Experiment Report",
        "",
        "## Summary",
        f"- total proposals: {total}",
        f"- committed: {committed}",
        f"- rejected: {rejected}",
        f"- rejection by gate: {dict(sorted(rejection_by_gate.items()))}",
        "",
        "## Cases",
        "| case_name | expected_gate | actual_status | failed_gate | passed |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['case_name']} | {row['expected_gate']} | {row['actual_status']} | "
            f"{row['failed_gate']} | {row['passed']} |"
        )

    counts = _counts(storage)
    lines.extend(
        [
            "",
            "## Invariant Check",
            f"∀ supports, raw chunk substring equals SpanRef.quote: {invariant_ok}",
            "",
            "## Idempotence Check",
            (
                "Repeated valid proposal does not duplicate claim/support: "
                f"{idempotence_ok} ({counts['claims']} claims, {counts['supports']} supports, "
                f"{counts['audit_events']} audit events after retry check)"
            ),
            "",
            "## Known Limitations",
            "- Gate 4 mock canonicalization is semantically weak.",
            "- Normalized matching is exact after normalization, not fuzzy.",
            "- Discontiguous quote handling only supports literal \"...\".",
            "- Character offsets are Python character offsets, not byte offsets.",
            "- No hypothesis/conflict/verdict layer yet.",
            "",
            "## Conclusion",
            "This MVP demonstrates deterministic rejection of ungrounded LLM evidence proposals.",
            "",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
