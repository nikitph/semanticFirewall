from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

from app.models import Chunk, EvidenceDraft


@dataclass(frozen=True)
class GeneratedProposal:
    generator_name: str
    draft_json: str
    cost_usd: float = 0.0


class ProposalGenerator(Protocol):
    name: str

    def propose(self, chunk: Chunk) -> list[GeneratedProposal]:
        ...


class RuleProposalGenerator:
    name = "RuleProposalGenerator"

    def propose(self, chunk: Chunk) -> list[GeneratedProposal]:
        sentence = _first_sentence(chunk.text)
        if not sentence:
            return []
        draft = EvidenceDraft(
            content=sentence,
            source_chunk_id=chunk.chunk_id,
            quoted_spans=[sentence],
        )
        return [_proposal(self.name, draft)]


class ManualGoldProposalGenerator:
    name = "ManualGoldProposalGenerator"

    def __init__(self, drafts_by_chunk_id: dict[str, list[EvidenceDraft]]):
        self.drafts_by_chunk_id = drafts_by_chunk_id

    def propose(self, chunk: Chunk) -> list[GeneratedProposal]:
        return [
            _proposal(self.name, draft)
            for draft in self.drafts_by_chunk_id.get(chunk.chunk_id, [])
        ]


class FixtureProposalGenerator:
    def __init__(
        self,
        *,
        name: str,
        draft_json_by_chunk_id: dict[str, list[str]],
        cost_per_proposal_usd: float = 0.0,
    ):
        self.name = name
        self.draft_json_by_chunk_id = draft_json_by_chunk_id
        self.cost_per_proposal_usd = cost_per_proposal_usd

    def propose(self, chunk: Chunk) -> list[GeneratedProposal]:
        return [
            GeneratedProposal(
                generator_name=self.name,
                draft_json=draft_json,
                cost_usd=self.cost_per_proposal_usd,
            )
            for draft_json in self.draft_json_by_chunk_id.get(chunk.chunk_id, [])
        ]


class LLMStructuredProposalGenerator(FixtureProposalGenerator):
    def __init__(
        self,
        draft_json_by_chunk_id: dict[str, list[str]],
        cost_per_proposal_usd: float = 0.002,
    ):
        super().__init__(
            name="LLMStructuredProposalGenerator",
            draft_json_by_chunk_id=draft_json_by_chunk_id,
            cost_per_proposal_usd=cost_per_proposal_usd,
        )


class OpenIEProposalGenerator(FixtureProposalGenerator):
    def __init__(self, draft_json_by_chunk_id: dict[str, list[str]]):
        super().__init__(
            name="OpenIEProposalGenerator",
            draft_json_by_chunk_id=draft_json_by_chunk_id,
            cost_per_proposal_usd=0.0,
        )


def evidence_draft_json(content: str, source_chunk_id: str, quoted_spans: list[str]) -> str:
    draft = EvidenceDraft(
        content=content,
        source_chunk_id=source_chunk_id,
        quoted_spans=quoted_spans,
    )
    return json.dumps(draft.model_dump(), ensure_ascii=False)


def _proposal(generator_name: str, draft: EvidenceDraft) -> GeneratedProposal:
    return GeneratedProposal(
        generator_name=generator_name,
        draft_json=json.dumps(draft.model_dump(), ensure_ascii=False),
    )


def _first_sentence(text: str) -> str:
    match = re.search(r".+?[.!?](?:\s|$)", text.strip(), flags=re.DOTALL)
    if match:
        return match.group(0).strip()
    return text.strip()
