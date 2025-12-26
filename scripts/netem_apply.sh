#!/usr/bin/env bash
set -euo pipefail
MODE="${1:-}"; IFACE="${2:-}"
if [[ -z "$MODE" || -z "$IFACE" ]]; then
  echo "Usage: $0 {baseline|stress1|clear} <iface>"; exit 1
fi
case "$MODE" in
  baseline) tc qdisc replace dev "$IFACE" root netem delay 5ms loss 0% ;;
  stress1)  tc qdisc replace dev "$IFACE" root netem delay 50ms 20ms distribution normal loss 0.5% ;;
  clear)    tc qdisc del dev "$IFACE" root netem 2>/dev/null || true ;;
  *) echo "Unknown mode: $MODE"; exit 2 ;;
esac
tc qdisc show dev "$IFACE"
