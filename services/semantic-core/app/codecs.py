import struct
from typing import Dict, Any

def lora_th_v1(payload: bytes) -> Dict[str, Any]:
    if len(payload) < 4: raise ValueError("short payload")
    temp_x100, hum_x10 = struct.unpack(">hH", payload[:4])
    return {"temp": temp_x100, "hum": hum_x10}

def zigbee_th_v1(payload: bytes) -> Dict[str, Any]:
    if len(payload) < 4: raise ValueError("short payload")
    t_x100, h_x10 = struct.unpack(">hH", payload[:4])
    return {"t": t_x100, "h": h_x10}

def ble_th_v1(payload: bytes) -> Dict[str, Any]:
    if len(payload) < 8: raise ValueError("short payload")
    temp, hum = struct.unpack(">ff", payload[:8])
    return {"temperature": float(temp), "humidity": float(hum)}

CODECS = {"lora_th_v1": lora_th_v1, "zigbee_th_v1": zigbee_th_v1, "ble_th_v1": ble_th_v1}
