import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

RUN = os.environ.get("RUN_ID", "local")
DIR = Path(os.environ.get("RUN_DIR", "artifacts/local"))
DIR.mkdir(parents=True, exist_ok=True)


def uid():
    return str(uuid.uuid4())


def log(component, kind, **fields):
    record = dict(
        run_id=RUN, component=component, kind=kind, wall_time=time.time(), **fields
    )
    with (DIR / f"{component}.jsonl").open("a") as f:
        f.write(json.dumps(record) + "\n")


def db(name):
    c = sqlite3.connect(DIR / f"{name}.sqlite", timeout=5, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=FULL")
    return c
