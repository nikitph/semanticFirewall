# Adapter Harness Report

## Summary
This experiment treats extractors as untrusted proposal generators. Each adapter emits draft JSON into the same Grounding Firewall runtime.

- committed blackboard claims: 5
- committed supports: 11
- audit events: 18

## Generator Metrics
generator | proposals | committed | rejected_gate_1 | rejected_gate_2 | rejected_gate_3 | unique_claims | duplicate_supports | cost_usd | latency_ms
--- | --- | --- | --- | --- | --- | --- | --- | --- | ---
RuleProposalGenerator | 4 | 4 | 0 | 0 | 0 | 4 | 0 | 0.0000 | 4.20
ManualGoldProposalGenerator | 4 | 4 | 0 | 0 | 0 | 4 | 0 | 0.0000 | 3.49
LLMStructuredProposalGenerator | 6 | 3 | 1 | 1 | 1 | 2 | 1 | 0.0120 | 5.64
OpenIEProposalGenerator | 4 | 3 | 0 | 0 | 1 | 3 | 0 | 0.0000 | 3.04

## Runtime Contract
- Same Gate 1 parsing path for every adapter.
- Same Gate 2 source-reference validation for every adapter.
- Same Gate 3 deterministic grounding for every adapter.
- Same ClaimID and SupportID hashing for every accepted proposal.
- Same append-only audit log for accepted and rejected proposals.
- Same provenance query surface after commit.

## Framing
NLP proposes. Transactional Cognition commits.
