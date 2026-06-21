from __future__ import annotations

from app.canonicalization import RuleCanonicalizer
from app.hashing import claim_id_for


def test_rule_canonicalizer_deduplicates_equivalent_revenue_claims():
    canonicalizer = RuleCanonicalizer()

    first = canonicalizer.canonicalize("Net revenue was $4M in FY2024.")
    second = canonicalizer.canonicalize("net revenue was $4m in FY2024")

    assert first == second
    assert first.subject == "net revenue"
    assert first.predicate == "equals"
    assert first.object == "$4M"
    assert first.temporal_bound == "FY2024"
    assert claim_id_for(first) == claim_id_for(second)


def test_rule_canonicalizer_keeps_different_numbers_separate():
    canonicalizer = RuleCanonicalizer()

    first = canonicalizer.canonicalize("Revenue was $3M.")
    second = canonicalizer.canonicalize("Revenue was $4M.")

    assert first.object == "$3M"
    assert second.object == "$4M"
    assert claim_id_for(first) != claim_id_for(second)
