import matplotlib
# ВМИКАЄМО РЕЖИМ БЕЗ ЕКРАНА (HEADLESS)
matplotlib.use('Agg') 

import matplotlib.pyplot as plt
import time
import json
import queue
import threading
import random
import struct
import numpy as np
from rdflib import Graph, Literal, RDF, URIRef, Namespace

# ==========================================
# PART 1: SETUP & ONTOLOGY GENERATION
# ==========================================
def create_knowledge_base():
    with open("ontology.ttl", "w") as f:
        f.write("""
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
        @prefix iot: <http://example.org/iot-ontology#> .
        iot:Device a rdfs:Class .
        iot:hasPhyID a rdf:Property .
        iot:usesCodec a rdf:Property .
        """)

    with open("inventory.ttl", "w") as f:
        f.write("""
        @prefix iot: <http://example.org/iot-ontology#> .
        @prefix ex: <http://example.org/site-1/> .
        
        ex:dev_lora_01 a iot:Device ;
            iot:hasPhyID "26011A2B" ; 
            iot:usesCodec "codec_lora_lht65" .

        ex:dev_zig_02 a iot:Device ;
            iot:hasPhyID "A1B2" ;
            iot:usesCodec "codec_zigbee_switch" .
            
        ex:dev_ble_03 a iot:Device ;
            iot:hasPhyID "AABBCCDDEEFF" ;
            iot:usesCodec "codec_ble_gatt" .
        """)

create_knowledge_base()

IOT = Namespace("http://example.org/iot-ontology#")
g = Graph()
try:
    g.parse("ontology.ttl", format="turtle")
    g.parse("inventory.ttl", format="turtle")
except:
    pass

# ==========================================
# PART 2: CODECS & GENERATORS
# ==========================================
def codec_lora(payload):
    if len(payload) < 2: raise ValueError("Short payload")
    return {"val": int.from_bytes(payload[0:2], 'big') / 100.0}

def codec_zigbee(payload):
    if len(payload) < 4: raise ValueError("Short payload")
    return {"status": "ON" if payload[3] == 1 else "OFF"}

def codec_ble(payload):
    try: return {"temp": round(struct.unpack('<f', payload)[0], 2)}
    except: return {"temp": 0.0}

CODECS = {"codec_lora_lht65": codec_lora, "codec_zigbee_switch": codec_zigbee, "codec_ble_gatt": codec_ble}

# Generators (FIXED HEX ERRORS)
def gen_lora(addr="26011A2B", malformed=False):
    pl = bytes.fromhex("FF") if malformed else int(2455).to_bytes(2, 'big')
    # Fixed MIC
    return bytes.fromhex("40" + addr + "00010002") + pl + bytes.fromhex("AABBCCDD")

def gen_zigbee(addr="A1B2"):
    return bytes.fromhex("61880112340000" + addr + "00060101" + "FFFF")

def gen_ble(mac="AABBCCDDEEFF"):
    # Fixed CRC
    return bytes.fromhex("8E89BED60216070004001B") + struct.pack('<f', 36.6) + bytes.fromhex("FFFFFF")

# ==========================================
# PART 3: RUNTIME ENGINE
# ==========================================
acp_queue = queue.Queue()
stop_event = threading.Event()

breakdown_data = {"LoRaWAN": [], "ZigBee": [], "BLE": []}
latency_hist_data = []
counters = {"ok": 0, "alien": 0, "malformed": 0, "cache_hit": 0, "cache_miss": 0}

class Packet:
    def __init__(self, pid, pl, proto):
        self.pid = pid; self.pl = pl; self.proto = proto; self.ts = time.perf_counter()

def run_core():
    cache = {}
    while not stop_event.is_set():
        try: pkt = acp_queue.get(timeout=0.1)
        except: continue
        
        t0 = time.perf_counter()
        
        # 1. LOOKUP
        codec_f = cache.get(pkt.pid)
        if codec_f:
            counters["cache_hit"] += 1
        else:
            counters["cache_miss"] += 1
            uri = next(g.subjects(IOT.hasPhyID, Literal(pkt.pid)), None)
            if uri:
                c_name = str(next(g.objects(uri, IOT.usesCodec), None))
                if c_name in CODECS:
                    codec_f = CODECS[c_name]
                    cache[pkt.pid] = codec_f
            
            if not codec_f:
                counters["alien"] += 1
                acp_queue.task_done(); continue

        t1 = time.perf_counter()

        # 2. DECODE
        try:
            res = codec_f(pkt.pl)
        except:
            counters["malformed"] += 1
            acp_queue.task_done(); continue
        t2 = time.perf_counter()

        # 3. SERIALIZE
        _ = json.dumps({"t": f"u/{pkt.proto}/{pkt.pid}", "v": res})
        t3 = time.perf_counter()

        d_q = (t0 - pkt.ts) * 1000
        d_l = (t1 - t0) * 1000
        d_d = (t2 - t1) * 1000
        d_s = (t3 - t2) * 1000
        
        breakdown_data[pkt.proto].append((d_q, d_l, d_d, d_s))
        latency_hist_data.append(d_q + d_l + d_d + d_s)
        counters["ok"] += 1
        acp_queue.task_done()

def run_agent(raw, proto, mac_meta=None):
    t_in = time.perf_counter()
    try:
        if proto == "LoRaWAN": pid, pl = raw[1:5].hex().upper(), raw[9:-4]
        elif proto == "ZigBee": pid, pl = raw[7:9].hex().upper(), raw[9:-2]
        elif proto == "BLE": pid, pl = mac_meta, raw[11:-3]
        
        p = Packet(pid, pl, proto)
        p.ts = t_in
        acp_queue.put(p)
    except: pass

# ==========================================
# PART 4: EXECUTION
# ==========================================
threading.Thread(target=run_core, daemon=True).start()

print(f">>> Running on RPi 5 (1200 packets)...")
for _ in range(1200):
    r = random.random()
    if r < 0.7:
        rp = random.random()
        if rp < 0.33: run_agent(gen_lora(), "LoRaWAN")
        elif rp < 0.66: run_agent(gen_zigbee(), "ZigBee")
        else: run_agent(gen_ble(), "BLE", "AABBCCDDEEFF")
    elif r < 0.9:
        run_agent(gen_lora("DEADBEEF"), "LoRaWAN")
    else:
        run_agent(gen_lora("26011A2B", True), "LoRaWAN")
    
    # Високе навантаження (~200 пакетів/сек)
    time.sleep(random.expovariate(200))

acp_queue.join()
stop_event.set()

# ==========================================
# PART 5: PLOTTING (FILES ONLY)
# ==========================================
print(f"\nResults: OK={counters['ok']}, Alien={counters['alien']}, Bad={counters['malformed']}")

def plot_breakdown():
    protocols = ["LoRaWAN", "ZigBee", "BLE"]
    components = ['Queue', 'Lookup', 'Decode', 'Serial']
    colors = ['#d3d3d3', '#1f77b4', '#ff7f0e', '#2ca02c']
    
    means = {p: np.mean(breakdown_data[p], axis=0) for p in protocols}
    vals = [[means[p][i] for p in protocols] for i in range(4)]
    
    plt.figure(figsize=(9, 6), dpi=300)
    ind = np.arange(3); width = 0.6; bottom = np.zeros(3)
    for i in range(4):
        plt.bar(ind, vals[i], width, bottom=bottom, color=colors[i], label=components[i], edgecolor='black')
        bottom += vals[i]
        
    plt.title('Avg Latency Breakdown @ RPi 5', fontweight='bold')
    plt.ylabel('Time (ms)', fontweight='bold')
    plt.xticks(ind, protocols, fontweight='bold')
    plt.legend()
    plt.grid(axis='y', linestyle=':', alpha=0.6)
    plt.tight_layout()
    plt.savefig('results/fig_latency_breakdown.png')
    print("Saved: fig_latency_breakdown.png")
    plt.close()

def plot_robustness():
    plt.figure(figsize=(9, 6), dpi=300)
    plt.hist(latency_hist_data, bins=50, color='#1f77b4', edgecolor='black', alpha=0.7)
    
    mean_val = np.mean(latency_hist_data)
    plt.title(f'End-to-End Latency Distribution @ RPi 5\n(Mean: {mean_val:.3f} ms)', fontweight='bold')
    plt.xlabel('Latency (ms)', fontweight='bold')
    plt.ylabel('Count', fontweight='bold')
    plt.grid(linestyle=':', alpha=0.6)
    plt.axvline(mean_val, color='red', linestyle='dashed')
    
    plt.tight_layout()
    plt.savefig('results/fig_robustness.png')
    print("Saved: fig_robustness.png")
    plt.close()

plot_breakdown()
plot_robustness()
