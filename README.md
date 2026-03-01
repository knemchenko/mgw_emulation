# mgw_emulation — Experiments

This repository contains reproducible experiments related to the M-GW / Semantic Protocol Translator (SPT) used in the 6G‑GUIDENET context (6G‑U / edge‑to‑cloud data delivery).

## Experiments

### Experiment 1 — Semantic Protocol Translator (Baseline & Paper Reproducibility)
Contains the core Python implementation of the Semantic Core and the simulation scripts used for architectural validation in our research papers.

This baseline module covers:
- **Internal Latency & Robustness:** Benchmarking the "Lookup → Decode → Serialize" hot path and security filtering on Raspberry Pi 5. (**IEEE BlackSeaCom 2025**)
- **Traffic Scalability Analysis:** Emulation of publisher-side traffic amplification comparing UNS (Fan-out) vs P2P (Tenant-Isolated) models. (**ICECET 2026**)

**Location:** `experiment1/`  
**Key Scripts:** `gateway_perf.py`, `scalability_test.py`
### Expirement 2 — Uplink scalability: gateway-side replication vs UNS fan-out (Raspberry Pi ↔ Server)
A reproducible testbed that compares two delivery policies for semantic updates over MQTT:

- **replication**: the gateway publishes **N_app** times (per-tenant topics) → uplink scales ~O(N_app)
- **uns**: the gateway publishes **once** into a **Unified Namespace (UNS)** topic → broker fan-out handles multiple consumers

Metrics collected:
- Raspberry Pi (publisher): interface-level uplink TX (kbps), CPU time, publish counters
- Server (subscriber): one-way latency percentiles (p50/p95/p99), max/mean, message loss proxy
- Post-processing: `merged.csv` + plots in `figures/`

See: `expirement2/README.md`

## Repository layout

- `expirement1/` — baseline (original repo content moved here)
- `expirement2/` — uplink-suite experiment (raspberry/server scripts + reproduction guide)

## Hardware & Environment
- **Reference Hardware:** Raspberry Pi 5 (Broadcom BCM2712, Cortex-A76 @ 2.4GHz)
- **Environment:** Python 3.x
- **Dependencies:** `paho-mqtt`, `matplotlib`, `numpy` (install via `pip install -r requirements.txt`)

---