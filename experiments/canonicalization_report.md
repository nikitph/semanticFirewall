# Canonicalization Evaluation Report

## Summary
Gate 4 remains untrusted: each canonicalizer is evaluated as a proposal generator whose output must pass `CanonicalClaim` validation before hashing or commit.

| canonicalizer | schema_pass_rate | predicate_quality | dedup_rate | false_split_rate | false_merge_rate |
| --- | --- | --- | --- | --- | --- |
| MockCanonicalizer | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 |
| RuleCanonicalizer | 1.00 | 1.00 | 1.00 | 0.00 | 0.00 |
| LLMCanonicalizer | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |

## Dataset
- cases: 13
- gold clusters define expected claim equivalence classes.

## Per-Case Outputs

### MockCanonicalizer
| case | gold_cluster | schema_passed | claim_id_prefix | canonical_claim_or_error |
| --- | --- | --- | --- | --- |
| revenue canonical | net-revenue-4m-fy2024 | True | 9fb17191afc8 | `{"subject": "unknown", "predicate": "states", "object": "Net revenue was $4M in FY2024.", "temporal_bound": null}` |
| revenue equivalent lowercase | net-revenue-4m-fy2024 | True | 70fe2f2ea6b8 | `{"subject": "unknown", "predicate": "states", "object": "net revenue was $4m in FY2024", "temporal_bound": null}` |
| revenue different amount | net-revenue-5m-fy2024 | True | 14f68fb78b56 | `{"subject": "unknown", "predicate": "states", "object": "Net revenue was $5M in FY2024.", "temporal_bound": null}` |
| revenue different year | net-revenue-4m-fy2025 | True | 9ad18c532825 | `{"subject": "unknown", "predicate": "states", "object": "Net revenue was $4M in FY2025.", "temporal_bound": null}` |
| gross margin canonical | gross-margin-61 | True | b9355599800d | `{"subject": "unknown", "predicate": "states", "object": "Gross margin was 61%.", "temporal_bound": null}` |
| gross margin equivalent | gross-margin-61 | True | bbba74eab4c2 | `{"subject": "unknown", "predicate": "states", "object": "gross margin was 61%", "temporal_bound": null}` |
| gross margin different value | gross-margin-16 | True | 387948a5de21 | `{"subject": "unknown", "predicate": "states", "object": "Gross margin was 16%.", "temporal_bound": null}` |
| acquisition canonical | acme-acquired-betaco | True | d6cb562cd1c7 | `{"subject": "unknown", "predicate": "states", "object": "Acme acquired BetaCo.", "temporal_bound": null}` |
| acquisition equivalent | acme-acquired-betaco | True | 746b086498ba | `{"subject": "unknown", "predicate": "states", "object": "ACME acquired betaco", "temporal_bound": null}` |
| acquisition different object | acme-acquired-gammaco | True | 61a2fca7c4f3 | `{"subject": "unknown", "predicate": "states", "object": "Acme acquired GammaCo.", "temporal_bound": null}` |
| bookings q4 canonical | bookings-increased-q4 | True | fa97e7894a29 | `{"subject": "unknown", "predicate": "states", "object": "Bookings increased in Q4.", "temporal_bound": null}` |
| bookings q4 equivalent | bookings-increased-q4 | True | 8ebd42bf4be5 | `{"subject": "unknown", "predicate": "states", "object": "bookings increased in Q4", "temporal_bound": null}` |
| bookings q3 different | bookings-increased-q3 | True | bce510317590 | `{"subject": "unknown", "predicate": "states", "object": "Bookings increased in Q3.", "temporal_bound": null}` |

### RuleCanonicalizer
| case | gold_cluster | schema_passed | claim_id_prefix | canonical_claim_or_error |
| --- | --- | --- | --- | --- |
| revenue canonical | net-revenue-4m-fy2024 | True | 5f490aa75fcc | `{"subject": "net revenue", "predicate": "equals", "object": "$4M", "temporal_bound": "FY2024"}` |
| revenue equivalent lowercase | net-revenue-4m-fy2024 | True | 5f490aa75fcc | `{"subject": "net revenue", "predicate": "equals", "object": "$4M", "temporal_bound": "FY2024"}` |
| revenue different amount | net-revenue-5m-fy2024 | True | 729db0f1bec0 | `{"subject": "net revenue", "predicate": "equals", "object": "$5M", "temporal_bound": "FY2024"}` |
| revenue different year | net-revenue-4m-fy2025 | True | ea78ee5c0404 | `{"subject": "net revenue", "predicate": "equals", "object": "$4M", "temporal_bound": "FY2025"}` |
| gross margin canonical | gross-margin-61 | True | 51a530873160 | `{"subject": "gross margin", "predicate": "equals", "object": "61%", "temporal_bound": null}` |
| gross margin equivalent | gross-margin-61 | True | 51a530873160 | `{"subject": "gross margin", "predicate": "equals", "object": "61%", "temporal_bound": null}` |
| gross margin different value | gross-margin-16 | True | 605c9d0b0602 | `{"subject": "gross margin", "predicate": "equals", "object": "16%", "temporal_bound": null}` |
| acquisition canonical | acme-acquired-betaco | True | 9a9e06004302 | `{"subject": "acme", "predicate": "acquired", "object": "betaco", "temporal_bound": null}` |
| acquisition equivalent | acme-acquired-betaco | True | 9a9e06004302 | `{"subject": "acme", "predicate": "acquired", "object": "betaco", "temporal_bound": null}` |
| acquisition different object | acme-acquired-gammaco | True | 4aa35415946a | `{"subject": "acme", "predicate": "acquired", "object": "gammaco", "temporal_bound": null}` |
| bookings q4 canonical | bookings-increased-q4 | True | bc3be7c51ba7 | `{"subject": "bookings", "predicate": "increased", "object": "true", "temporal_bound": "Q4"}` |
| bookings q4 equivalent | bookings-increased-q4 | True | bc3be7c51ba7 | `{"subject": "bookings", "predicate": "increased", "object": "true", "temporal_bound": "Q4"}` |
| bookings q3 different | bookings-increased-q3 | True | b5581bc3ba38 | `{"subject": "bookings", "predicate": "increased", "object": "true", "temporal_bound": "Q3"}` |

### LLMCanonicalizer
| case | gold_cluster | schema_passed | claim_id_prefix | canonical_claim_or_error |
| --- | --- | --- | --- | --- |
| revenue canonical | net-revenue-4m-fy2024 | False |  | `"LLM canonicalizer is not configured for this offline implementation."` |
| revenue equivalent lowercase | net-revenue-4m-fy2024 | False |  | `"LLM canonicalizer is not configured for this offline implementation."` |
| revenue different amount | net-revenue-5m-fy2024 | False |  | `"LLM canonicalizer is not configured for this offline implementation."` |
| revenue different year | net-revenue-4m-fy2025 | False |  | `"LLM canonicalizer is not configured for this offline implementation."` |
| gross margin canonical | gross-margin-61 | False |  | `"LLM canonicalizer is not configured for this offline implementation."` |
| gross margin equivalent | gross-margin-61 | False |  | `"LLM canonicalizer is not configured for this offline implementation."` |
| gross margin different value | gross-margin-16 | False |  | `"LLM canonicalizer is not configured for this offline implementation."` |
| acquisition canonical | acme-acquired-betaco | False |  | `"LLM canonicalizer is not configured for this offline implementation."` |
| acquisition equivalent | acme-acquired-betaco | False |  | `"LLM canonicalizer is not configured for this offline implementation."` |
| acquisition different object | acme-acquired-gammaco | False |  | `"LLM canonicalizer is not configured for this offline implementation."` |
| bookings q4 canonical | bookings-increased-q4 | False |  | `"LLM canonicalizer is not configured for this offline implementation."` |
| bookings q4 equivalent | bookings-increased-q4 | False |  | `"LLM canonicalizer is not configured for this offline implementation."` |
| bookings q3 different | bookings-increased-q3 | False |  | `"LLM canonicalizer is not configured for this offline implementation."` |
