import os, random
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from common.logging_utils import now_ms, log_event

LOG_DIR = os.getenv("LOG_DIR", "/logs/identity-manager")
PORT = int(os.getenv("PORT", "8001"))

app = FastAPI(title="Identity Manager", version="0.1")

REG_BY_PHY = {}
REG_BY_LOGICAL = {}

def assign_vip() -> str:
    return f"10.0.0.{random.randint(10, 250)}"

def model_for_protocol(protocol: str) -> str:
    return {
        "lora": "http://example.org/iot#Model_LoRa_TempHum",
        "zigbee": "http://example.org/iot#Model_ZigBee_TempHum",
        "ble": "http://example.org/iot#Model_BLE_TempHum",
    }.get(protocol, "http://example.org/iot#Model_Unknown")

class RegisterReq(BaseModel):
    protocol: str
    phy_id: str
    logical_id: str

class RegisterResp(BaseModel):
    logical_id: str
    phy_id: str
    vip: str
    model_uri: str
    ts_registered: int

@app.post("/register", response_model=RegisterResp)
def register(req: RegisterReq):
    ts = now_ms()
    vip = assign_vip()
    model_uri = model_for_protocol(req.protocol)
    old_phy = REG_BY_LOGICAL.get(req.logical_id)
    if old_phy and old_phy != req.phy_id:
        REG_BY_PHY.pop(old_phy, None)
    rec = {
        "protocol": req.protocol,
        "phy_id": req.phy_id,
        "logical_id": req.logical_id,
        "vip": vip,
        "model_uri": model_uri,
        "ts_registered": ts,
    }
    REG_BY_PHY[req.phy_id] = rec
    REG_BY_LOGICAL[req.logical_id] = req.phy_id
    log_event(LOG_DIR, "events.jsonl", {"ts": ts, "event": "register", **rec, "old_phy": old_phy})
    return rec

@app.get("/resolve/by-phy/{phy_id}")
def resolve_by_phy(phy_id: str):
    ts = now_ms()
    rec = REG_BY_PHY.get(phy_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Unknown phy_id")
    log_event(LOG_DIR, "events.jsonl", {"ts": ts, "event": "resolve_by_phy", "phy_id": phy_id})
    return rec

@app.get("/health")
def health():
    return {"ok": True, "registered": len(REG_BY_PHY)}

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, log_level="info")
