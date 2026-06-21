from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

from app.canonicalization import LLMCanonicalizer, MockCanonicalizer, RuleCanonicalizer
from app.exceptions import GateException
from app.hashing import claim_id_for
from app.models import CanonicalClaim


ROOT = Path(__file__).resolve().parent
CASES_PATH = ROOT / "canonicalization_cases.json"
REPORT_PATH = ROOT / "canonicalization_report.md"


def main() -> None:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    canonicalizers = {
        "MockCanonicalizer": MockCanonicalizer(),
        "RuleCanonicalizer": RuleCanonicalizer(),
        "LLMCanonicalizer": LLMCanonicalizer(client=None),
    }

    results = {
        name: evaluate_canonicalizer(name, canonicalizer, cases)
        for name, canonicalizer in canonicalizers.items()
    }
    _print_summary(results)
    _write_report(results, cases)
    print(f"\nWrote {REPORT_PATH}")


def evaluate_canonicalizer(name: str, canonicalizer: Any, cases: list[dict[str, str]]) -> dict[str, Any]:
    rows = []
    for case in cases:
        try:
            claim = canonicalizer.canonicalize(case["content"])
            claim = CanonicalClaim.model_validate(claim.model_dump())
            rows.append(
                {
                    "case_name": case["case_name"],
                    "gold_cluster": case["gold_cluster"],
                    "schema_passed": True,
                    "predicate_quality": _predicate_is_normalized(claim.predicate),
                    "claim_id": claim_id_for(claim),
                    "canonical_claim": claim.model_dump(),
                    "error": None,
                }
            )
        except (GateException, Exception) as exc:
            rows.append(
                {
                    "case_name": case["case_name"],
                    "gold_cluster": case["gold_cluster"],
                    "schema_passed": False,
                    "predicate_quality": False,
                    "claim_id": None,
                    "canonical_claim": None,
                    "error": str(exc),
                }
            )

    pair_metrics = _pair_metrics(rows)
    schema_passes = sum(1 for row in rows if row["schema_passed"])
    predicate_passes = sum(1 for row in rows if row["predicate_quality"])
    return {
        "name": name,
        "rows": rows,
        "schema_pass_rate": schema_passes / len(rows),
        "predicate_normalization_quality": predicate_passes / len(rows),
        **pair_metrics,
    }


def _predicate_is_normalized(predicate: str) -> bool:
    return bool(predicate) and predicate == predicate.lower() and " " not in predicate


def _pair_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    same_gold_pairs = 0
    same_gold_merged = 0
    same_gold_split = 0
    different_gold_pairs = 0
    different_gold_merged = 0

    passed_rows = [row for row in rows if row["schema_passed"]]
    for left, right in itertools.combinations(passed_rows, 2):
        same_gold = left["gold_cluster"] == right["gold_cluster"]
        same_claim = left["claim_id"] == right["claim_id"]
        if same_gold:
            same_gold_pairs += 1
            if same_claim:
                same_gold_merged += 1
            else:
                same_gold_split += 1
        else:
            different_gold_pairs += 1
            if same_claim:
                different_gold_merged += 1

    return {
        "claim_deduplication_rate": _rate(same_gold_merged, same_gold_pairs),
        "false_split_rate": _rate(same_gold_split, same_gold_pairs),
        "false_merge_rate": _rate(different_gold_merged, different_gold_pairs),
    }


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _print_summary(results: dict[str, dict[str, Any]]) -> None:
    print(
        "canonicalizer | schema_pass_rate | predicate_quality | "
        "dedup_rate | false_split_rate | false_merge_rate"
    )
    print("--- | --- | --- | --- | --- | ---")
    for result in results.values():
        print(
            f"{result['name']} | {result['schema_pass_rate']:.2f} | "
            f"{result['predicate_normalization_quality']:.2f} | "
            f"{result['claim_deduplication_rate']:.2f} | "
            f"{result['false_split_rate']:.2f} | {result['false_merge_rate']:.2f}"
        )


def _write_report(results: dict[str, dict[str, Any]], cases: list[dict[str, str]]) -> None:
    lines = [
        "# Canonicalization Evaluation Report",
        "",
        "## Summary",
        (
            "Gate 4 remains untrusted: each canonicalizer is evaluated as a proposal generator whose "
            "output must pass `CanonicalClaim` validation before hashing or commit."
        ),
        "",
        "| canonicalizer | schema_pass_rate | predicate_quality | dedup_rate | false_split_rate | false_merge_rate |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for result in results.values():
        lines.append(
            f"| {result['name']} | {result['schema_pass_rate']:.2f} | "
            f"{result['predicate_normalization_quality']:.2f} | "
            f"{result['claim_deduplication_rate']:.2f} | "
            f"{result['false_split_rate']:.2f} | {result['false_merge_rate']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Dataset",
            f"- cases: {len(cases)}",
            "- gold clusters define expected claim equivalence classes.",
            "",
            "## Per-Case Outputs",
        ]
    )
    for result in results.values():
        lines.extend(
            [
                "",
                f"### {result['name']}",
                "| case | gold_cluster | schema_passed | claim_id_prefix | canonical_claim_or_error |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for row in result["rows"]:
            claim_or_error = row["canonical_claim"] if row["canonical_claim"] else row["error"]
            claim_id_prefix = row["claim_id"][:12] if row["claim_id"] else ""
            lines.append(
                f"| {row['case_name']} | {row['gold_cluster']} | {row['schema_passed']} | "
                f"{claim_id_prefix} | `{json.dumps(claim_or_error, ensure_ascii=False)}` |"
            )

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
