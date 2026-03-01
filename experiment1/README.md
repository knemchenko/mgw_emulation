# Experiment 1 — Semantic Protocol Translator (Baseline)

This directory contains the core implementation and experimental scripts for the **Semantic Protocol Translator** architecture. It serves as the code basis for the evaluation sections of two research papers.

## Hardware & Environment
- **Reference Hardware:** Raspberry Pi 5 (Broadcom BCM2712, Cortex-A76 @ 2.4GHz)
- **Environment:** Python 3.x
- **Dependencies:** `paho-mqtt`, `matplotlib`, `numpy` (install via `pip install -r requirements.txt`)

---

## Experiments & Usage

This repository includes two main experimental scripts corresponding to the evaluation sections of the research papers.

### 1. Latency & Robustness Analysis
Measures the internal processing latency of the Semantic Core (Lookup → Decode → Serialize) and validates the LRU caching mechanism under stochastic load.

* **Target:** Real-time performance validation
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

* **Target:** Architectural scalability quantification 
* **Script:** `src/scalability_test.py`
* **Output:**
  * `fig_scalability_pubs.png` (MQTT Publish count comparison)
  * `fig_scalability_bytes.png` (Traffic volume comparison)
  * `fig_scalability_normalized.png` (Overhead per semantic update)

**To run:**
```bash
python src/scalability_test.py
```


## Repository Structure

- **`src/`** — Source code and execution scripts.
  - `gateway_perf.py`: Latency benchmark script.
  - `scalability_test.py`: Scalability comparison script.
  - `core/`, `agents/`, `utils/`: Internal modules.
- **`results/`** — Generated charts, histograms, and logs.
