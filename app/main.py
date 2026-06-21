from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from app.canonicalization import MockCanonicalizer
from app.exceptions import GateException
from app.models import IngestRequest, ProposeFailureResponse, ProposeRequest
from app.pipeline import Pipeline
from app.storage import Storage


storage = Storage()
storage.init_db()
pipeline = Pipeline(storage=storage, canonicalizer=MockCanonicalizer())

app = FastAPI(title="Grounding Firewall v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest")
def ingest(request: IngestRequest) -> dict[str, int | str]:
    for chunk in request.chunks:
        storage.upsert_chunk(chunk)
    return {"status": "ok", "ingested": len(request.chunks)}


@app.post("/propose")
def propose(request: ProposeRequest):
    try:
        return pipeline.process_draft(request.draft_json)
    except GateException as exc:
        response = ProposeFailureResponse(
            status="rejected",
            failed_gate=exc.gate_number,
            reason=exc.reason,
            details=exc.details,
        )
        return JSONResponse(status_code=200, content=response.model_dump())


@app.get("/graph")
def graph():
    return storage.get_graph_summary()


@app.get("/claims/{claim_id}/provenance")
def claim_provenance(claim_id: str):
    provenance = storage.get_claim_provenance(claim_id)
    if provenance is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return provenance


@app.get("/certificates")
def transition_certificates():
    return {"certificates": storage.get_transition_certificates()}
