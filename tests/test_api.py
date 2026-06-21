from __future__ import annotations

import importlib
import json

from fastapi.testclient import TestClient


def test_api_ingest_propose_reject_graph_and_health(tmp_path, monkeypatch):
    monkeypatch.setenv("GROUNDING_FIREWALL_DB_PATH", str(tmp_path / "api.db"))
    import app.main as main

    main = importlib.reload(main)
    client = TestClient(main.app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    ingest = client.post(
        "/ingest",
        json={
            "chunks": [
                {
                    "chunk_id": "chunk-1",
                    "text": "Net revenue was $4M in FY2024.",
                }
            ]
        },
    )
    assert ingest.status_code == 200
    assert ingest.json() == {"status": "ok", "ingested": 1}

    success_draft = {
        "content": "Net revenue was $4M in FY2024.",
        "source_chunk_id": "chunk-1",
        "quoted_spans": ["Net revenue was $4M in FY2024"],
    }
    proposed = client.post("/propose", json={"draft_json": json.dumps(success_draft)})
    assert proposed.status_code == 200
    proposed_json = proposed.json()
    assert proposed_json["status"] == "committed"

    rejected_draft = {
        "content": "Net revenue was $5M in FY2024.",
        "source_chunk_id": "chunk-1",
        "quoted_spans": ["Net revenue was $5M"],
    }
    rejected = client.post("/propose", json={"draft_json": json.dumps(rejected_draft)})
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["failed_gate"] == 3

    graph = client.get("/graph")
    assert graph.status_code == 200
    graph_json = graph.json()
    assert graph_json["claim_count"] == 1
    assert graph_json["support_count"] == 1
    assert graph_json["claims"][0]["support_count"] == 1

    provenance = client.get(f"/claims/{proposed_json['claim_id']}/provenance")
    assert provenance.status_code == 200
    provenance_json = provenance.json()
    assert provenance_json["claim_id"] == proposed_json["claim_id"]
    assert provenance_json["support_count"] == 1
    assert provenance_json["supports"][0]["source_chunk_id"] == "chunk-1"
    assert provenance_json["supports"][0]["span_refs"][0] == {
        "start_index": 0,
        "end_index": 29,
        "quote": "Net revenue was $4M in FY2024",
    }

    missing = client.get("/claims/not-a-real-claim/provenance")
    assert missing.status_code == 404
