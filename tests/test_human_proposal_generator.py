from __future__ import annotations

import json

from app.models import Chunk
from app.proposals import HumanProposalGenerator


def test_human_proposal_generator_loads_json_file(tmp_path):
    proposal_file = tmp_path / "human_proposals.json"
    proposal_file.write_text(
        json.dumps(
            {
                "chunks": [
                    {
                        "chunk_id": "chunk-1",
                        "drafts": [
                            {
                                "content": "Revenue was $3M.",
                                "source_chunk_id": "chunk-1",
                                "quoted_spans": ["Revenue was $3M"],
                            }
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    generator = HumanProposalGenerator(proposal_file)
    proposals = generator.propose(Chunk(chunk_id="chunk-1", text="Revenue was $3M."))

    assert generator.name == "HumanProposalGenerator"
    assert len(proposals) == 1
    assert proposals[0].generator_name == "HumanProposalGenerator"
    assert json.loads(proposals[0].draft_json)["quoted_spans"] == ["Revenue was $3M"]
