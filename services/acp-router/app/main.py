import os
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn, httpx
from common.logging_utils import now_ms, log_event

LOG_DIR = os.getenv("LOG_DIR", "/logs/acp-router")
PORT = int(os.getenv("PORT", "8002"))
SEMANTIC_CORE_URL = os.getenv("SEMANTIC_CORE_URL", "http://semantic-core:8003")

app = FastAPI(title="ACP Router Stub", version="0.1")

class IngestReq(BaseModel):
    protocol: str
    phy_id: str
    trace_id: str
    seq: int
    ts_gen: int
    payload_b64: str
    retries: int = 0

@app.post("/ingest")
async def ingest(req: IngestReq):
    ts = now_ms()
    log_event(LOG_DIR, "events.jsonl", {"ts": ts, "event": "acp_in", **req.model_dump()})
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{SEMANTIC_CORE_URL}/ingest", json={**req.model_dump(), "ts_acp_in": ts})
        r.raise_for_status()
        return r.json()

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, log_level="info")
