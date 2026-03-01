import matplotlib
matplotlib.use('Agg') # Headless mode for RPi

import matplotlib.pyplot as plt
import time
import json
import queue
import threading
import random

# --- CONFIGURATION ---
APP_COUNT = 10         # Кількість додатків-споживачів
WINDOW_SEC = 60        # Час вимірювання (секунди)
INGEST_RATE = 2.0      # ~2 пакети в секунду (імітація вхідного потоку)

# --- METRICS STORAGE ---
# UNS Mode: 1 publish per update
# P2P Mode: N publishes per update (N = APP_COUNT)
results = {
    "uns": {"pubs": 0, "bytes": 0, "ingested": 0},
    "p2p": {"pubs": 0, "bytes": 0, "ingested": 0}
}

def run_simulation(mode):
    print(f"--- Running {mode.upper()} simulation (Apps={APP_COUNT}, Time={WINDOW_SEC}s) ---")
    
    start_time = time.time()
    pub_count = 0
    byte_count = 0
    ingest_count = 0
    
    while time.time() - start_time < WINDOW_SEC:
        # 1. Ingest simulated packet
        payload = {"temp": round(random.uniform(20.0, 30.0), 2), "hum": 60}
        payload_json = json.dumps(payload)
        payload_len = len(payload_json.encode('utf-8'))
        ingest_count += 1
        
        # 2. Publish Logic
        if mode == "uns":
            # UNS: Publish once to unified topic
            # Topic: "mgw/site1/sensor01" (~20 bytes)
            # Overhead estimate: Topic + Fixed Header (~25 bytes total usually, but we count App Payload)
            # In paper we count APPLICATION PAYLOAD BYTES (Body)
            pub_count += 1
            byte_count += payload_len
            
        elif mode == "p2p":
            # P2P: Publish to EACH app specific topic
            for i in range(APP_COUNT):
                pub_count += 1
                byte_count += payload_len 
        
        # Sleep to simulate arrival rate
        time.sleep(1.0 / INGEST_RATE)
        
    return {"pubs": pub_count, "bytes": byte_count, "ingested": ingest_count}

# --- EXECUTION ---
print(f">>> Starting Scalability Experiment on Raspberry Pi 5...")

# Run UNS
results["uns"] = run_simulation("uns")
time.sleep(1) # Cooldown

# Run P2P
results["p2p"] = run_simulation("p2p")

# --- RESULTS OUTPUT ---
print("\n=== RESULTS ===")
print(f"UNS: {results['uns']['pubs']} pubs, {results['uns']['bytes']} bytes (Ingested: {results['uns']['ingested']})")
print(f"P2P: {results['p2p']['pubs']} pubs, {results['p2p']['bytes']} bytes (Ingested: {results['p2p']['ingested']})")

# --- PLOTTING ---
def plot_charts():
    modes = ['UNS', 'P2P']
    
    # 1. Publish Operations Count (Fig 4a)
    plt.figure(figsize=(8, 6))
    vals_pubs = [results['uns']['pubs'], results['p2p']['pubs']]
    bars = plt.bar(modes, vals_pubs, color=['#1f77b4', '#d62728'])
    plt.title(f'Publisher-side Publishes (60s, Apps={APP_COUNT}) @ RPi 5')
    plt.ylabel('Count')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval, int(yval), ha='center', va='bottom')
        
    plt.savefig('results/fig_scalability_pubs.png')
    plt.close()
    
    # 2. Traffic Volume Bytes (Fig 4b)
    plt.figure(figsize=(8, 6))
    vals_bytes = [results['uns']['bytes'], results['p2p']['bytes']]
    bars = plt.bar(modes, vals_bytes, color=['#1f77b4', '#d62728'])
    plt.title(f'Publisher-side Traffic Volume (60s, Apps={APP_COUNT}) @ RPi 5')
    plt.ylabel('Bytes')
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval, int(yval), ha='center', va='bottom')

    plt.savefig('results/fig_scalability_bytes.png')
    plt.close()

    # 3. Normalized Overhead (Fig 5 - old numbering)
    # Bytes per Ingested Update
    plt.figure(figsize=(8, 6))
    norm_uns = results['uns']['bytes'] / results['uns']['ingested']
    norm_p2p = results['p2p']['bytes'] / results['p2p']['ingested']
    
    vals_norm = [norm_uns, norm_p2p]
    bars = plt.bar(modes, vals_norm, color=['#1f77b4', '#d62728'])
    plt.title(f'Normalized Overhead per Semantic Update (Apps={APP_COUNT}) @ RPi 5')
    plt.ylabel('Bytes / Ingested Frame')
    plt.grid(axis='y', linestyle='--', alpha=0.7)

    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval, f"{yval:.1f}", ha='center', va='bottom')

    plt.savefig('results/fig_scalability_normalized.png')
    plt.close()

plot_charts()
print("\nGraphs saved: fig_scalability_pubs.png, fig_scalability_bytes.png, fig_scalability_normalized.png")
