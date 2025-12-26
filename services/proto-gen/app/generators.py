import struct, random

def make_payload(protocol: str, payload_bytes: int) -> bytes:
    temp_c = random.uniform(18.0, 30.0)
    hum_p = random.uniform(35.0, 75.0)
    if protocol in ("lora", "zigbee"):
        temp_x100 = int(round(temp_c * 100))
        hum_x10 = int(round(hum_p * 10))
        base = struct.pack(">hH", temp_x100, hum_x10)
    elif protocol == "ble":
        base = struct.pack(">ff", float(temp_c), float(hum_p))
    else:
        base = b""
    if payload_bytes <= len(base):
        return base[:payload_bytes]
    return base + bytes(payload_bytes - len(base))
