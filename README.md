# Semantic Protocol Translator for 6G-U Networks: Reference Implementation

This repository contains the reference software implementation and evaluation scripts for the **Intelligent Multiprotocol Mesh Gateway (M-GW)** architecture described in our research.

The project emulates a **Semantic Core** that provides:
1.  **Bearer Independent Communication (BIC):** Decoupling application logic from physical radio protocols (LoRaWAN, ZigBee, BLE).
2.  **Semantic Contract Invariance:** Normalizing heterogeneous payloads into a stable Unified Namespace (UNS).
3.  **Ontology-Driven Validation:** Dynamic decoding and validation using a Knowledge Graph.

## Related Publications

This code supports the experimental results presented in:
* **"Architecture of Multiprotocol Translator for 6G-U Networks: An Ontological Approach"** (Submitted to IEEE BlackSeaCom 2026 / ICECET 2026).

## Hardware Setup

The performance benchmarks were conducted on the following reference hardware:
* **Device:** Raspberry Pi 5 Model B
* **SoC:** Broadcom BCM2712 (Quad-core Cortex-A76 @ 2.4GHz)
* **RAM:** 8GB LPDDR4X
* **OS:** Raspberry Pi OS (64-bit, Bookworm)

## Installation

1. Clone the repository:
   ```bash
   git clone [https://github.com/your-username/6g-semantic-gateway.git](https://github.com/your-username/6g-semantic-gateway.git)
   cd 6g-semantic-gateway
   ```
   
2. Create a virtual environment:
    ```bash 
    python3 -m venv venv
    source venv/bin/activate
   ```
3. Install dependencies
    ```bash 
    pip install -r requirements.txt
   ```
## Experiments & Usage

This repository includes two main experimental scripts corresponding to the evaluation sections of the paper.

1. Latency & Robustness Analysis
This repository includes two main experimental scripts corresponding to the evaluation sections of the research papers.

### 1. Latency & Robustness Analysis
Measures the internal processing latency of the Semantic Core (Lookup → Decode → Serialize) and validates the LRU caching mechanism under stochastic load.

* **Target:** Real-time performance validation (Paper Section VII-A in BlackSeaCom submission).
* **Script:** `src/gateway_perf.py`
* **Output:**
  * `fig_latency_breakdown.png` (Processing time per stage)
  * `fig_robustness.png` (End-to-end latency histogram)

**To run:**
```bash
  python src/gateway_perf.py
```

### 2. Scalability Analysis (UNS vs P2P)
Quantifies publisher-side traffic amplification by comparing the proposed Unified Namespace (Fan-out) model against a Tenant-Isolated (Point-to-Point) baseline.

* **Target:** Architectural scalability quantification (Paper Section VII-A in ICECET submission).
* **Script:** `src/scalability_test.py`
* **Output:**
  * `fig_scalability_pubs.png` (MQTT Publish count comparison)
  * `fig_scalability_bytes.png` (Traffic volume comparison)
  * `fig_scalability_normalized.png` (Overhead per semantic update)

**To run:**
```bash
  python src/scalability_test.py
```

# License
This project is licensed under the MIT License - see the LICENSE file for details.