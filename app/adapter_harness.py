from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from app.exceptions import GateException
from app.models import Chunk
from app.pipeline import Pipeline
from app.proposals import ProposalGenerator


@dataclass
class GeneratorMetrics:
    generator: str
    proposals: int = 0
    committed: int = 0
    rejected_gate_1: int = 0
    rejected_gate_2: int = 0
    rejected_gate_3: int = 0
    rejected_gate_4: int = 0
    rejected_gate_5: int = 0
    unique_claims: int = 0
    duplicate_supports: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0


def run_generator_harness(
    *,
    chunks: list[Chunk],
    generators: list[ProposalGenerator],
    pipeline: Pipeline,
) -> list[GeneratorMetrics]:
    rows: list[GeneratorMetrics] = []

    for generator in generators:
        metrics = GeneratorMetrics(generator=generator.name)
        seen_claim_ids: set[str] = set()
        seen_support_ids: set[str] = set()
        started = perf_counter()

        for chunk in chunks:
            proposals = generator.propose(chunk)
            metrics.proposals += len(proposals)
            for proposal in proposals:
                metrics.cost_usd += proposal.cost_usd
                try:
                    response = pipeline.process_draft(proposal.draft_json)
                    metrics.committed += 1
                    seen_claim_ids.add(response.claim_id)
                    if response.support_id in seen_support_ids:
                        metrics.duplicate_supports += 1
                    seen_support_ids.add(response.support_id)
                except GateException as exc:
                    _increment_gate(metrics, exc.gate_number)

        metrics.unique_claims = len(seen_claim_ids)
        metrics.latency_ms = (perf_counter() - started) * 1000
        rows.append(metrics)

    return rows


def _increment_gate(metrics: GeneratorMetrics, gate_number: int) -> None:
    if gate_number == 1:
        metrics.rejected_gate_1 += 1
    elif gate_number == 2:
        metrics.rejected_gate_2 += 1
    elif gate_number == 3:
        metrics.rejected_gate_3 += 1
    elif gate_number == 4:
        metrics.rejected_gate_4 += 1
    elif gate_number == 5:
        metrics.rejected_gate_5 += 1
