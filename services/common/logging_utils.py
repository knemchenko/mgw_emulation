import json, time, uuid
from pathlib import Path
from typing import Any, Dict

def now_ms() -> int:
    return int(time.time() * 1000)

def ensure_dir(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)

def log_event(log_dir: str, filename: str, event: Dict[str, Any]) -> None:
    ensure_dir(log_dir)
    p = Path(log_dir) / filename
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

def new_trace_id() -> str:
    return str(uuid.uuid4())
