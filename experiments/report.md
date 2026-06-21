# Grounding Firewall v1 Experiment Report

## Summary
- total proposals: 6
- committed: 4
- rejected: 2
- rejection by gate: {2: 1, 3: 1}

## Cases
| case_name | expected_gate | actual_status | failed_gate | passed |
| --- | --- | --- | --- | --- |
| valid exact quote | None | committed | None | True |
| valid whitespace normalization | None | committed | None | True |
| valid smart punctuation normalization | None | committed | None | True |
| valid ellipsis quote | None | committed | None | True |
| invalid phantom chunk ID | 2 | rejected | 2 | True |
| invalid hallucinated quote | 3 | rejected | 3 | True |

## Invariant Check
∀ supports, raw chunk substring equals SpanRef.quote: True

## Idempotence Check
Repeated valid proposal does not duplicate claim/support: True (4 claims, 4 supports, 8 audit events after retry check)

## Known Limitations
- Gate 4 mock canonicalization is semantically weak.
- Normalized matching is exact after normalization, not fuzzy.
- Discontiguous quote handling only supports literal "...".
- Character offsets are Python character offsets, not byte offsets.
- No hypothesis/conflict/verdict layer yet.

## Conclusion
This MVP demonstrates deterministic rejection of ungrounded LLM evidence proposals.
