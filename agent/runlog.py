"""Writes every step of a run as one JSON line. The metrics are computed later
from these files."""

import json
import time
from pathlib import Path


class RunLog:
    def __init__(self, folder, name):
        Path(folder).mkdir(parents=True, exist_ok=True)
        self.path = Path(folder) / f"{time.strftime('%Y%m%d-%H%M%S')}_{name}.jsonl"
        self.start = time.time()

    def write(self, kind, **data):
        line = {"t": round(time.time() - self.start, 2), "kind": kind, **data}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
