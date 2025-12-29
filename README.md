# MGW Emulation Testbed (Protocol Agents → ACP Stub → Semantic Core → UNS/MQTT)

This repository provides a Docker-based emulation testbed to evaluate an M-GW pipeline:
multi-protocol ingestion → ACP routing stub → ontology-driven Semantic Core → northbound MQTT/UNS.

It is intended to generate reproducible, paper-ready metrics (e.g., traffic amplification in UNS vs P2P duplication).

## What is included

- **Protocol generators** (LoRa-like, ZigBee-like, BLE-like): emit UDP frames at controlled rates.
- **Protocol Agents**: receive UDP, attach trace metadata, and forward to ACP.
- **ACP Router (stub)**: forwards to the Semantic Core.
- **Semantic Core**: decodes frames (ontology-driven or hardcoded) and publishes to MQTT.
- **MQTT broker (Mosquitto)**: provides the UNS pub/sub fabric.
- **Application subscribers**: scale-out consumers for fan-out experiments.

## Requirements

- Docker Desktop (or Docker Engine)
- Docker Compose v2
- Python 3.10+ (for evaluation scripts)

## Configuration (.env)

Docker Compose automatically loads a local `.env`. Use the provided template:

1) Copy:
```bash
cp .env.example .env
```

2) Adjust parameters:

- `APP_COUNT`: number of application subscribers (A).
- `P2P_MODE`:
  - `0` = UNS mode (Semantic Core publishes once to `mgw/...`, broker performs fan-out).
  - `1` = P2P duplication (Semantic Core publishes to `mgw_p2p/appN/...` per app).
- `DECODER_MODE`: `ontology` (default) or `hardcoded`.
- `RUN_DURATION_SEC`: fixed experiment duration in seconds.
- `START_DELAY_SEC`: optional generator delay before sending frames (helps ensure subscribers are ready).
- `REGISTER_TIMEOUT_SEC`: how long generators retry Identity Manager registration before failing.

**PowerShell note:** environment variables in the current shell can override `.env`.
If you previously ran `P2P_MODE=0 ...` style commands, open a new shell or remove `Env:P2P_MODE` / `Env:APP_COUNT`.

## Run

**If Docker Hub is temporarily unavailable** (e.g., TLS handshake timeout) and you already built the images once,
you can run without rebuilding:

```bash
docker compose up -d --no-build --scale app-subscriber=10
```

This repo includes a small `docker-compose.override.yml` that bind-mounts the generator entrypoint
(`services/proto-gen/app/main.py`) into the running containers. This makes small hotfixes possible even when you
cannot rebuild images.

### 1) Start the stack (scale subscribers)

From the repository root:
```bash
docker compose up --build --scale app-subscriber=10  # set to the same value as APP_COUNT in .env
```

Alternatively, run detached:
```bash
docker compose up -d --build --scale app-subscriber=10  # set to the same value as APP_COUNT in .env
```

The protocol generators and subscribers stop automatically after `RUN_DURATION_SEC`.
Infrastructure services (broker, core, agents) keep running until you stop them.

Stop everything:
```bash
docker compose down -v
```

### 2) Health check

Semantic Core:
```bash
curl http://localhost:8003/health
```

## Exp2: Traffic amplification (UNS vs P2P)

### Recommended procedure (clean runs)

Before each run:
```bash
docker compose down -v
rm -rf ./logs ./results
mkdir -p ./results
```

Run (UNS):
- Set `P2P_MODE=0` in `.env`
- Start:
```bash
docker compose up -d --build --scale app-subscriber=10  # set to the same value as APP_COUNT in .env
```

Run (P2P):
- Set `P2P_MODE=1` in `.env`
- Start:
```bash
docker compose up -d --build --scale app-subscriber=10  # set to the same value as APP_COUNT in .env
```

### Evaluate

After the run completes (or after waiting `RUN_DURATION_SEC`), compute metrics:

```bash
python tools/eval_exp2_traffic.py --logs ./logs --out ./results/exp2.json --window-sec 60  # set to RUN_DURATION_SEC
```

Output fields:
- `publisher.messages`, `publisher.bytes`: total gateway→broker publish overhead (Semantic Core publishes).
- `subscriber.messages`: total messages received across all application subscribers.
- `topic_histogram_top10`: busiest topics (all publishes).
- `telemetry.publisher.*`, `telemetry.subscriber.*`, `telemetry.topic_histogram_top10`: telemetry-only breakdown (topics ending with `/telemetry`).
- `frames.ingested_estimate`: estimated number of ingested frames in the window (unique `ts_core_in`).
- `derived.publisher_msgs_per_frame`: publish overhead normalized per ingested frame (≈ 1 for UNS, ≈ APP_COUNT for P2P).
- `derived.subscriber_msgs_per_published_msg`: fan-out indicator (≈ APP_COUNT in UNS with `APP_COUNT` subscribers).
- `derived.window_sec`: analysis window length.

## Logs

All services write JSONL logs into `./logs/<service>/events.jsonl`.

The evaluator uses:
- `logs/**/semantic-core/events.jsonl` (publish events)
- `logs/**/app-subscriber/events.jsonl` (recv events)