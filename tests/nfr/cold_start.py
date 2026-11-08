"""NFR-7 cold start: time from process start to the first 200 on /healthz, budget 60 s.

Starts uvicorn exactly as ``playwright.config.ts`` does (same module, host, port and
``M12_DB_PATH=:memory:``), then polls ``/healthz`` against a bounded deadline. No sleep: each probe
has its own timeout, and the gap between probes is an Event wait that ends early if set.

Run: ``.venv/bin/python tests/nfr/cold_start.py`` (exit 0 when the budget holds).
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

BUDGET_SECONDS = 60.0
HOST, PORT = "127.0.0.1", 8000
URL = f"http://{HOST}:{PORT}/healthz"
PROBE_INTERVAL_SECONDS = 0.1
PROBE_TIMEOUT_SECONDS = 1.0
ROOT = Path(__file__).resolve().parents[2]


def healthz_answers_200() -> bool:
    try:
        with urllib.request.urlopen(URL, timeout=PROBE_TIMEOUT_SECONDS) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def main() -> int:
    env = {**os.environ, "M12_DB_PATH": ":memory:"}
    command = [
        sys.executable, "-m", "uvicorn", "src.adapters.inbound.app:create_app",
        "--factory", "--host", HOST, "--port", str(PORT), "--log-level", "warning",
    ]  # fmt: skip
    if healthz_answers_200():
        print(f"cold start not measured: {URL} already answers; stop the other server first")
        return 2
    started = time.monotonic()
    server = subprocess.Popen(command, cwd=ROOT, env=env)  # noqa: S603
    wait = threading.Event()  # the probe gap; never a fixed sleep
    try:
        while True:
            elapsed = time.monotonic() - started
            if healthz_answers_200():
                break
            if server.poll() is not None:
                print(f"server exited with {server.returncode} before /healthz answered")
                return 1
            if elapsed >= BUDGET_SECONDS:
                print(f"/healthz did not answer within {BUDGET_SECONDS:.0f} s")
                return 1
            wait.wait(PROBE_INTERVAL_SECONDS)
        cold_start = time.monotonic() - started
    finally:
        server.terminate()
        server.wait(timeout=10)
    verdict = "PASS" if cold_start <= BUDGET_SECONDS else "FAIL"
    print(f"command: {' '.join(command[1:])}")
    print(f"M12_DB_PATH=:memory:  url={URL}")
    print(f"cold start to first 200 on /healthz: {cold_start:.2f} s (budget {BUDGET_SECONDS:.0f} s)")
    print(f"NFR-7 cold start: {verdict}")
    return 0 if cold_start <= BUDGET_SECONDS else 1


if __name__ == "__main__":
    raise SystemExit(main())
